from django.db.models import Q
from django.utils import timezone

from apps.tenant.attendance.models import AttendanceEntry
from apps.tenant.finance.invoicing import invoice_amounts
from apps.tenant.finance.models import Invoice, OutboundMessageLog
from apps.tenant.finance.services import _dispatch_to_phone
from apps.tenant.finance.communication_providers import send_email_notice
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User

from .models import Conversation, Message


def user_label(user):
    return user.get_full_name() or user.get_username()


def scoped_recipients(*, audience_role, campus=None, class_group=None, stream=None, balance_status="", attendance_status=""):
    users = User.objects.filter(is_active=True)
    if audience_role and audience_role != "ALL":
        users = users.filter(roles__code=audience_role)
    if audience_role == Role.PARENT:
        parent_qs = ParentProfile.objects.filter(is_active=True, user__isnull=False)
        if campus or class_group or stream:
            links = ParentStudentLink.objects.filter(parent__in=parent_qs)
            if campus:
                links = links.filter(student__campus=campus)
            if class_group:
                links = links.filter(student__stream__class_group=class_group)
            if stream:
                links = links.filter(student__stream=stream)
            parent_qs = parent_qs.filter(id__in=links.values_list("parent_id", flat=True))
        if balance_status:
            parent_ids = set()
            for parent in parent_qs:
                student_ids = ParentStudentLink.objects.filter(parent=parent).values_list("student_id", flat=True)
                invoices = Invoice.objects.filter(student_id__in=student_ids).prefetch_related("lines", "payments")
                ok = False
                for inv in invoices:
                    amounts = invoice_amounts(inv)
                    if balance_status == "OUTSTANDING" and amounts.balance > 0:
                        ok = True
                    elif balance_status == "OVERDUE" and amounts.is_overdue:
                        ok = True
                    elif balance_status == "PAID" and amounts.balance <= 0:
                        ok = True
                if ok:
                    parent_ids.add(parent.id)
            parent_qs = parent_qs.filter(id__in=parent_ids)
        users = users.filter(id__in=parent_qs.values_list("user_id", flat=True))
    elif audience_role == Role.STUDENT:
        students = StudentProfile.objects.filter(is_active=True, user__isnull=False)
        if campus:
            students = students.filter(campus=campus)
        if class_group:
            students = students.filter(stream__class_group=class_group)
        if stream:
            students = students.filter(stream=stream)
        users = users.filter(id__in=students.values_list("user_id", flat=True))
    elif audience_role == Role.TEACHER:
        teachers = TeacherProfile.objects.filter(is_active=True, user__isnull=False)
        if campus:
            teachers = teachers.filter(campus=campus)
        users = users.filter(id__in=teachers.values_list("user_id", flat=True))
    if attendance_status:
        today = timezone.localdate()
        student_ids = AttendanceEntry.objects.filter(session__date=today, status=attendance_status).values_list("student_id", flat=True)
        if audience_role == Role.PARENT:
            users = users.filter(parent_profile__parentstudentlink__student_id__in=student_ids)
        elif audience_role == Role.STUDENT:
            users = users.filter(student_profile__id__in=student_ids)
    return users.distinct().order_by("first_name", "last_name", "username")


def send_internal_bulk_message(*, sender, recipients, subject, body):
    sent = 0
    for recipient in recipients:
        convo = Conversation.objects.create(subject=subject, created_by=sender)
        convo.participants.add(sender, recipient)
        Message.objects.create(conversation=convo, sender=sender, content=body)
        sent += 1
    return sent


def send_external_bulk_message(*, recipients, channel, subject, body, dry_run=False):
    sent = failed = skipped = 0
    details = []
    for user in recipients:
        phone = ""
        email = user.email or ""
        parent = getattr(user, "parent_profile", None)
        teacher = getattr(user, "teacher_profile", None)
        student = getattr(user, "student_profile", None)
        if parent:
            phone = parent.phone or ""
            email = parent.email or email
        elif teacher:
            phone = teacher.phone or ""
            email = teacher.email or email
        elif student:
            phone = getattr(student, "phone", "") or ""
        if channel == "EMAIL":
            result = send_email_notice(email, subject, body)
            ok = result.get("ok")
        else:
            if not phone:
                skipped += 1
                details.append({"user": user_label(user), "status": "no_phone"})
                continue
            result = _dispatch_to_phone(message_type=OutboundMessageLog.URGENT_ANNOUNCEMENT, channel=channel, phone=phone, message=body, provider_response_extra={"bulk": True, "subject": subject}, dry_run=dry_run)
            ok = result.get("status") in ["sent", "dry_run"]
        if ok:
            sent += 1
        else:
            failed += 1
        details.append({"user": user_label(user), "status": "sent" if ok else "failed"})
    return {"sent": sent, "failed": failed, "skipped": skipped, "details": details}


def send_bulk_message(*, sender, form_data):
    recipients = scoped_recipients(audience_role=form_data["audience_role"], campus=form_data.get("campus"), class_group=form_data.get("class_group"), stream=form_data.get("stream"), balance_status=form_data.get("balance_status") or "", attendance_status=form_data.get("attendance_status") or "")
    channel = form_data["channel"]
    if channel == "INBOX":
        return {"recipients": recipients.count(), "sent": send_internal_bulk_message(sender=sender, recipients=recipients, subject=form_data["subject"], body=form_data["message"]), "failed": 0, "skipped": 0}
    result = send_external_bulk_message(recipients=recipients, channel=channel, subject=form_data["subject"], body=form_data["message"], dry_run=form_data.get("dry_run"))
    result["recipients"] = recipients.count()
    return result
