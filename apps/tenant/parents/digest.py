from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from apps.tenant.announcements.models import Announcement
from apps.tenant.attendance.models import AttendanceEntry
from apps.tenant.coursework.models import Assignment, AssignmentSubmission
from apps.tenant.discipline.models import Incident
from apps.tenant.exams.models import ExamSchedule, SeatAllocation
from apps.tenant.finance.models import Invoice
from apps.tenant.orgsettings.models import Notification
from apps.tenant.orgsettings.utils import create_notification, log_action
from apps.tenant.portals.push_delivery import send_web_push_to_user

from .models import ParentDigest, ParentProfile, ParentStudentLink


@dataclass(frozen=True)
class DigestWindow:
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.start:%b %d} - {self.end:%b %d, %Y}"


def default_digest_window(today: date | None = None, days: int = 7) -> DigestWindow:
    end = today or timezone.localdate()
    return DigestWindow(start=end - timedelta(days=days - 1), end=end)


def _student_name(student) -> str:
    return student.get_full_name() if hasattr(student, "get_full_name") else str(student)


def _money(value: Decimal) -> str:
    return f"{value:,.0f}" if value == value.quantize(Decimal("1")) else f"{value:,.2f}"


def _assignment_queryset_for_student(student, window: DigestWindow):
    now = timezone.now()
    qs = Assignment.objects.filter(is_active=True, publish_at__lte=now).filter(
        Q(stream=student.stream)
        | Q(class_group=getattr(student.stream, "class_group", None))
        | Q(offering__class_group=getattr(student.stream, "class_group", None))
    )
    return qs.filter(Q(due_date__date__gte=window.start, due_date__date__lte=window.end + timedelta(days=7)) | Q(due_date__isnull=True)).distinct()


def build_parent_digest(parent: ParentProfile, *, window: DigestWindow | None = None, campus_scope=None) -> dict:
    window = window or default_digest_window()
    links = (
        ParentStudentLink.objects.filter(parent=parent)
        .select_related("student", "student__stream", "student__stream__class_group", "student__campus")
        .order_by("-is_primary", "student__last_name", "student__first_name")
    )
    if campus_scope is not None:
        links = links.filter(student__campus=campus_scope)
    students = []
    total_balance = Decimal("0")
    total_absences = 0
    total_due_assignments = 0
    total_incidents = 0

    for link in links:
        student = link.student
        attendance = AttendanceEntry.objects.filter(student=student, session__date__gte=window.start, session__date__lte=window.end)
        attendance_total = attendance.count()
        absent_count = attendance.filter(status=AttendanceEntry.ABSENT).count()
        late_count = attendance.filter(status=AttendanceEntry.LATE).count()
        present_like = attendance.filter(status__in=[AttendanceEntry.PRESENT, AttendanceEntry.LATE, AttendanceEntry.EXCUSED]).count()
        attendance_rate = round((present_like / attendance_total) * 100) if attendance_total else None

        invoices = Invoice.objects.filter(student=student).prefetch_related("lines", "payments")
        balance = sum((invoice.balance() for invoice in invoices if invoice.status == Invoice.ACTIVE), Decimal("0"))
        overdue_count = sum(1 for invoice in invoices if invoice.status == Invoice.ACTIVE and invoice.due_date and invoice.due_date < window.end and invoice.balance() > 0)

        assignments = list(_assignment_queryset_for_student(student, window).order_by("due_date", "-publish_at")[:10])
        submitted_ids = set(
            AssignmentSubmission.objects.filter(student=student, assignment__in=assignments, submitted_at__isnull=False).values_list("assignment_id", flat=True)
        )
        due_assignments = [assignment for assignment in assignments if assignment.id not in submitted_ids]

        incidents = list(
            Incident.objects.filter(student=student)
            .filter(Q(incident_date__gte=window.start, incident_date__lte=window.end) | Q(incident_date__isnull=True, created_at__date__gte=window.start, created_at__date__lte=window.end))
            .order_by("-incident_date", "-created_at")[:5]
        )

        schedules = list(
            ExamSchedule.objects.filter(
                seat_allocations__student=student,
                date__gte=window.end,
                date__lte=window.end + timedelta(days=14),
            )
            .select_related("paper", "paper__exam", "paper__offering", "paper__offering__course")
            .distinct()
            .order_by("date", "start_time")[:5]
        )
        seat_map = {
            allocation.schedule_id: allocation.seat_number
            for allocation in SeatAllocation.objects.filter(student=student, schedule__in=schedules)
        }

        total_balance += balance
        total_absences += absent_count
        total_due_assignments += len(due_assignments)
        total_incidents += len(incidents)

        students.append(
            {
                "student": student,
                "name": _student_name(student),
                "campus": student.campus,
                "attendance_total": attendance_total,
                "attendance_rate": attendance_rate,
                "absent_count": absent_count,
                "late_count": late_count,
                "balance": balance,
                "balance_display": _money(balance),
                "overdue_count": overdue_count,
                "due_assignments": due_assignments,
                "incidents": incidents,
                "exam_schedules": schedules,
                "seat_map": seat_map,
            }
        )

    announcements = list(
        Announcement.objects.filter(is_active=True, created_at__date__gte=window.start, created_at__date__lte=window.end)
        .filter(Q(audience=Announcement.ALL) | Q(audience=Announcement.PARENTS))
        .order_by("-is_urgent", "-created_at")[:5]
    )

    subject = f"Weekly parent digest: {window.label}"
    lines = [subject]
    if not students:
        lines.append("No linked students were found for this parent profile.")
    for row in students:
        attendance_text = "No attendance recorded"
        if row["attendance_rate"] is not None:
            attendance_text = f"{row['attendance_rate']}% attendance, {row['absent_count']} absent, {row['late_count']} late"
        lines.append(
            f"{row['name']}: {attendance_text}; balance {row['balance_display']}; "
            f"{len(row['due_assignments'])} assignment(s) due; {len(row['incidents'])} discipline update(s); "
            f"{len(row['exam_schedules'])} upcoming exam(s)."
        )
    if announcements:
        lines.append("Announcements: " + "; ".join(item.title for item in announcements))

    return {
        "parent": parent,
        "window": window,
        "subject": subject,
        "message": "\n".join(lines),
        "students": students,
        "announcements": announcements,
        "totals": {
            "children": len(students),
            "balance": total_balance,
            "balance_display": _money(total_balance),
            "absences": total_absences,
            "due_assignments": total_due_assignments,
            "incidents": total_incidents,
        },
    }


def _parent_email(parent: ParentProfile) -> str:
    return (parent.email or getattr(parent.user, "email", "") or "").strip()


def _digest_totals_for_json(digest: dict) -> dict:
    totals = dict(digest["totals"])
    totals["balance"] = str(totals.get("balance", "0"))
    return totals


def _digest_record_for(parent: ParentProfile, digest: dict, *, created_by=None) -> tuple[ParentDigest, bool]:
    window = digest["window"]
    record, created = ParentDigest.objects.get_or_create(
        parent=parent,
        window_start=window.start,
        window_end=window.end,
        defaults={
            "subject": digest["subject"],
            "message": digest["message"],
            "totals": _digest_totals_for_json(digest),
            "created_by": created_by,
        },
    )
    if not created:
        record.subject = digest["subject"]
        record.message = digest["message"]
        record.totals = _digest_totals_for_json(digest)
    return record, created


def _send_digest_whatsapp(parent: ParentProfile, digest_record: ParentDigest, digest: dict, *, dry_run: bool = False) -> dict:
    from apps.tenant.finance.models import OutboundMessageLog
    from apps.tenant.finance.services import _create_outbound_log, _dispatch_to_phone

    channel = OutboundMessageLog.WHATSAPP
    if not parent.allow_whatsapp_alerts:
        return {"attempted": False, "sent": False, "reason": "Parent has not consented to WhatsApp alerts."}
    phone = (parent.phone or "").strip()
    if not phone:
        _create_outbound_log(
            message_type=OutboundMessageLog.PARENT_DIGEST,
            channel=channel,
            phone_raw="",
            status=OutboundMessageLog.NO_PHONE,
            message=digest["message"][:480],
            error_message=f"No phone for parent_id={parent.pk}",
            provider_response={"parent_digest_id": digest_record.pk, "parent_id": parent.pk},
        )
        return {"attempted": True, "sent": False, "status": "no_phone", "reason": "Parent has no phone number."}
    result = _dispatch_to_phone(
        message_type=OutboundMessageLog.PARENT_DIGEST,
        channel=channel,
        phone=phone,
        message=digest["message"][:480],
        provider_response_extra={"parent_digest_id": digest_record.pk, "parent_id": parent.pk},
        dry_run=dry_run,
    )
    return {
        "attempted": True,
        "sent": result.get("status") == "sent",
        "status": result.get("status", ""),
        "phone": phone,
        "phone_normalized": result.get("phone_normalized", ""),
    }


def _send_digest_email(parent: ParentProfile, digest: dict) -> dict:
    recipient = _parent_email(parent)
    result = {"attempted": True, "sent": False, "recipient": recipient}
    if not recipient:
        result["reason"] = "Parent has no email address."
        return result
    html_body = render_to_string("emails/parent_digest.html", {"digest": digest, "parent": parent})
    message = EmailMultiAlternatives(
        digest["subject"],
        digest["message"],
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [recipient],
    )
    message.attach_alternative(html_body, "text/html")
    result["sent"] = message.send(fail_silently=False) > 0
    return result


def send_parent_digest(
    parent: ParentProfile,
    *,
    created_by=None,
    window: DigestWindow | None = None,
    campus_scope=None,
    include_push: bool = True,
    include_email: bool = False,
    include_whatsapp: bool = False,
    whatsapp_dry_run: bool = False,
    force: bool = False,
    use_parent_preferences: bool = False,
) -> dict:
    digest = build_parent_digest(parent, window=window, campus_scope=campus_scope)
    if use_parent_preferences:
        if not parent.digest_enabled:
            reason = "Parent has disabled weekly digests."
            digest_record, _created = _digest_record_for(parent, digest, created_by=created_by)
            digest_record.status = ParentDigest.SKIPPED
            digest_record.channels = {"reason": reason}
            digest_record.save(update_fields=["subject", "message", "totals", "status", "channels", "updated_at"])
            log_action(
                parent,
                action="PARENT_DIGEST_SKIPPED",
                description=reason,
                user=created_by,
                metadata={"window": digest["window"].label, "parent_digest_id": digest_record.pk, "reason": reason},
            )
            return {"sent": False, "reason": reason, "digest": digest, "digest_record": digest_record}
        include_push = parent.digest_pwa_enabled
        include_email = parent.digest_email_enabled
        include_whatsapp = parent.digest_whatsapp_enabled
    digest_record, _created = _digest_record_for(parent, digest, created_by=created_by)
    if digest_record.status == ParentDigest.SENT and not force:
        reason = "Digest already sent for this parent and window."
        log_action(
            parent,
            action="PARENT_DIGEST_SKIPPED",
            description=reason,
            user=created_by,
            metadata={"window": digest["window"].label, "parent_digest_id": digest_record.pk, "reason": reason},
        )
        return {"sent": False, "duplicate": True, "reason": reason, "digest": digest, "digest_record": digest_record}
    if not parent.user_id:
        reason = "Parent has no linked user account."
        digest_record.status = ParentDigest.SKIPPED
        digest_record.channels = {"reason": reason}
        digest_record.save(update_fields=["subject", "message", "totals", "status", "channels", "updated_at"])
        log_action(
            parent,
            action="PARENT_DIGEST_SKIPPED",
            description=reason,
            user=created_by,
            metadata={"window": digest["window"].label, "parent_digest_id": digest_record.pk, "reason": reason},
        )
        return {"sent": False, "reason": reason, "digest": digest, "digest_record": digest_record}

    notification = create_notification(
        title=digest["subject"],
        message=digest["message"],
        recipient=parent.user,
        audience=Notification.PARENTS,
        priority=Notification.NORMAL,
        link="/parent/",
        created_by=created_by,
        expires_at=timezone.now() + timedelta(days=21),
    )
    push_result = {"attempted": 0, "sent": 0, "results": []}
    if include_push:
        push_result = send_web_push_to_user(
            parent.user,
            title="Weekly parent digest",
            body=digest["message"].splitlines()[1] if len(digest["message"].splitlines()) > 1 else digest["subject"],
            url="/parent/",
        )
    email_result = {"attempted": False, "sent": False, "recipient": ""}
    if include_email:
        email_result = _send_digest_email(parent, digest)
    whatsapp_result = {"attempted": False, "sent": False}
    if include_whatsapp:
        whatsapp_result = _send_digest_whatsapp(parent, digest_record, digest, dry_run=whatsapp_dry_run)

    digest_record.notification = notification
    digest_record.status = ParentDigest.SENT
    digest_record.sent_at = timezone.now()
    digest_record.created_by = digest_record.created_by or created_by
    digest_record.channels = {
        "portal": {"sent": True, "notification_id": notification.pk},
        "push": push_result,
        "email": email_result,
        "whatsapp": whatsapp_result,
    }
    digest_record.save(
        update_fields=[
            "subject",
            "message",
            "totals",
            "notification",
            "status",
            "sent_at",
            "created_by",
            "channels",
            "updated_at",
        ]
    )

    log_action(
        parent,
        action="PARENT_DIGEST_SENT",
        description=f"Smart Parent Digest sent for {digest['window'].label}.",
        user=created_by,
        metadata={
            "window": digest["window"].label,
            "parent_digest_id": digest_record.pk,
            "notification_id": notification.pk,
            "children": digest["totals"]["children"],
            "push_attempted": push_result.get("attempted", 0),
            "push_sent": push_result.get("sent", 0),
            "email_attempted": email_result.get("attempted", False),
            "email_sent": email_result.get("sent", False),
            "email_recipient": email_result.get("recipient", ""),
            "whatsapp_attempted": whatsapp_result.get("attempted", False),
            "whatsapp_sent": whatsapp_result.get("sent", False),
        },
    )
    return {
        "sent": True,
        "notification": notification,
        "push": push_result,
        "email": email_result,
        "whatsapp": whatsapp_result,
        "digest": digest,
        "digest_record": digest_record,
    }


def send_all_parent_digests(
    *,
    created_by=None,
    window: DigestWindow | None = None,
    campus_scope=None,
    include_push: bool = True,
    include_email: bool = False,
    include_whatsapp: bool = False,
    whatsapp_dry_run: bool = False,
    force: bool = False,
    active_only: bool = True,
    use_parent_preferences: bool = False,
) -> dict:
    qs = ParentProfile.objects.select_related("user").order_by("last_name", "first_name")
    if active_only:
        qs = qs.filter(is_active=True)
    if campus_scope is not None:
        qs = qs.filter(parentstudentlink__student__campus=campus_scope).distinct()
    results = [
        send_parent_digest(
            parent,
            created_by=created_by,
            window=window,
            campus_scope=campus_scope,
            include_push=include_push,
            include_email=include_email,
            include_whatsapp=include_whatsapp,
            whatsapp_dry_run=whatsapp_dry_run,
            force=force,
            use_parent_preferences=use_parent_preferences,
        )
        for parent in qs
    ]
    return {
        "attempted": len(results),
        "sent": sum(1 for item in results if item.get("sent")),
        "skipped": sum(1 for item in results if not item.get("sent")),
        "push_sent": sum((item.get("push") or {}).get("sent", 0) for item in results),
        "email_sent": sum(1 for item in results if (item.get("email") or {}).get("sent")),
        "whatsapp_sent": sum(1 for item in results if (item.get("whatsapp") or {}).get("sent")),
        "duplicates": sum(1 for item in results if item.get("duplicate")),
        "results": results,
    }
