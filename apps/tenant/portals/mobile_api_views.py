from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.announcements.models import Announcement
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.coursework.models import Assignment, AssignmentSubmission, LearningMaterial
from apps.tenant.coursework.services import visible_assignments_for_student, visible_materials_for_student
from apps.tenant.exams.models import Exam, ExamPaper, ExamScore, OnlineExamAttempt
from apps.tenant.exams.services import results_visible_for_paper
from apps.tenant.finance.invoicing import invoice_amounts
from apps.tenant.finance.models import Invoice, Payment
from apps.tenant.messaging.models import Conversation, Message
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.transport.models import StudentTransportAssignment
from apps.tenant.users.models import MobileDevice, Role


class MobileAPIView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]


def user_roles(user):
    return list(user.roles.values_list("code", flat=True))


def profile_for_user(user):
    data = {"user_id": user.id, "username": user.username, "email": user.email, "roles": user_roles(user)}
    student = StudentProfile.objects.filter(user=user).select_related("campus", "stream", "stream__class_group").first()
    teacher = TeacherProfile.objects.filter(user=user).select_related("campus").first()
    parent = ParentProfile.objects.filter(user=user).first()
    if student:
        data["student"] = serialize_student(student)
    if teacher:
        data["teacher"] = serialize_teacher(teacher)
    if parent:
        data["parent"] = serialize_parent(parent)
    return data


def serialize_student(s):
    return {"id": s.id, "student_id": s.student_id, "name": s.get_full_name(), "email": s.email, "campus": str(s.campus or ""), "stream": str(s.stream or ""), "class_group": str(s.stream.class_group) if s.stream else ""}


def serialize_teacher(t):
    return {"id": t.id, "staff_id": t.staff_id, "name": str(t), "phone": t.phone, "email": t.email, "campus": str(t.campus or "")}


def serialize_parent(p):
    return {"id": p.id, "name": str(p), "phone": p.phone, "email": p.email, "allow_sms_alerts": p.allow_sms_alerts, "allow_whatsapp_alerts": p.allow_whatsapp_alerts}


def linked_students_for_parent(parent):
    return StudentProfile.objects.filter(parentstudentlink__parent=parent).select_related("campus", "stream", "stream__class_group")


def students_for_mobile_user(user):
    student = StudentProfile.objects.filter(user=user).select_related("campus", "stream", "stream__class_group").first()
    if student:
        return StudentProfile.objects.filter(pk=student.pk)
    parent = ParentProfile.objects.filter(user=user).first()
    if parent:
        return linked_students_for_parent(parent)
    return StudentProfile.objects.none()


def teacher_for_user(user):
    return TeacherProfile.objects.filter(user=user).first()


def invoice_json(inv):
    amounts = invoice_amounts(inv)
    return {"id": inv.id, "reference": inv.reference, "student": serialize_student(inv.student), "academic_year": str(inv.academic_year or ""), "academic_term": str(inv.academic_term or ""), "due_date": inv.due_date, "status": inv.status, "total_amount": amounts.total_amount, "total_paid": amounts.total_paid, "balance": amounts.balance, "display_status": amounts.display_status, "overdue": amounts.overdue}


def payment_json(p):
    return {"id": p.id, "invoice_id": p.invoice_id, "student": serialize_student(p.invoice.student), "amount": p.amount, "method": p.method, "mobile_network": p.mobile_network, "reference": p.reference, "received_at": p.received_at, "created_at": p.created_at}


def paper_json(paper, student=None):
    attempt = None
    score = None
    if student:
        attempt = OnlineExamAttempt.objects.filter(paper=paper, student=student).first()
        if results_visible_for_paper(paper):
            score = ExamScore.objects.filter(paper=paper, student=student).first()
    return {"id": paper.id, "exam": str(paper.exam), "course": paper.offering.course.name, "mode": paper.exam.exam_mode, "duration_minutes": paper.duration_minutes, "is_published": paper.is_published, "results_published": paper.results_published, "attempt_status": attempt.status if attempt else None, "attempt_id": attempt.id if attempt else None, "score": score.score if score else None, "percentage": score.percentage if score else None, "grade": score.grade if score else ""}


class MobileMe(MobileAPIView):
    def get(self, request):
        return Response(profile_for_user(request.user))


class MobileDashboard(MobileAPIView):
    def get(self, request):
        students = list(students_for_mobile_user(request.user))
        teacher = teacher_for_user(request.user)
        data = {"profile": profile_for_user(request.user), "counts": {}}
        if students:
            invoices = Invoice.objects.filter(student__in=students).prefetch_related("lines", "payments")
            balances = [invoice_amounts(inv).balance for inv in invoices]
            data["students"] = [serialize_student(s) for s in students]
            data["counts"].update({"invoices": invoices.count(), "open_balance": sum(balances), "published_results": ExamScore.objects.filter(student__in=students, paper__results_published=True).count(), "coursework_items": sum(visible_materials_for_student(s).count() + visible_assignments_for_student(s).count() for s in students)})
        if teacher:
            offerings = CourseOffering.objects.filter(teacher=teacher, is_active=True)
            data["counts"].update({"teacher_offerings": offerings.count(), "attendance_sessions": AttendanceSession.objects.filter(offering__in=offerings).count(), "exam_papers": ExamPaper.objects.filter(offering__in=offerings).count()})
        data["announcements"] = list(Announcement.objects.filter(is_active=True).filter(Q(audience=Announcement.ALL) | Q(audience__in=user_roles(request.user))).values("id", "title", "body", "audience", "is_urgent", "created_at")[:10])
        return Response(data)


class MobileStudents(MobileAPIView):
    def get(self, request):
        students = students_for_mobile_user(request.user)
        teacher = teacher_for_user(request.user)
        if teacher and not students.exists():
            students = StudentProfile.objects.filter(enrollment__offering__teacher=teacher, enrollment__status=Enrollment.ACTIVE).distinct()
        return Response({"students": [serialize_student(s) for s in students]})


class MobileTeachers(MobileAPIView):
    def get(self, request):
        qs = TeacherProfile.objects.filter(is_active=True).select_related("campus")[:100]
        return Response({"teachers": [serialize_teacher(t) for t in qs]})


class MobileParents(MobileAPIView):
    def get(self, request):
        parent = ParentProfile.objects.filter(user=request.user).first()
        if parent:
            return Response({"parent": serialize_parent(parent), "students": [serialize_student(s) for s in linked_students_for_parent(parent)]})
        return Response({"parent": None, "students": []})


class MobileAttendance(MobileAPIView):
    def get(self, request):
        students = students_for_mobile_user(request.user)
        teacher = teacher_for_user(request.user)
        if teacher:
            offerings = CourseOffering.objects.filter(teacher=teacher, is_active=True).select_related("course", "term")
            sessions = AttendanceSession.objects.filter(offering__in=offerings).select_related("offering", "offering__course")[:50]
            return Response({"offerings": [{"id": o.id, "course": o.course.name, "term": str(o.term)} for o in offerings], "recent_sessions": [{"id": s.id, "offering": str(s.offering), "date": s.date} for s in sessions]})
        entries = AttendanceEntry.objects.filter(student__in=students).select_related("session", "session__offering", "session__offering__course")[:100]
        return Response({"entries": [{"id": e.id, "student": serialize_student(e.student), "date": e.session.date, "course": e.session.offering.course.name, "status": e.status, "note": e.note} for e in entries]})


class MobileTeacherAttendanceMark(MobileAPIView):
    def post(self, request, offering_id: int):
        teacher = teacher_for_user(request.user)
        if not teacher:
            return Response({"detail": "Teacher profile required."}, status=status.HTTP_403_FORBIDDEN)
        offering = get_object_or_404(CourseOffering, pk=offering_id, teacher=teacher, is_active=True)
        date_value = request.data.get("date") or timezone.now().date()
        session, _ = AttendanceSession.objects.get_or_create(offering=offering, date=date_value, defaults={"taken_by": teacher})
        saved = 0
        for row in request.data.get("entries", []):
            student_id = row.get("student_id")
            if not Enrollment.objects.filter(student_id=student_id, offering=offering, status=Enrollment.ACTIVE).exists():
                continue
            AttendanceEntry.objects.update_or_create(session=session, student_id=student_id, defaults={"status": row.get("status") or AttendanceEntry.PRESENT, "note": row.get("note") or ""})
            saved += 1
        return Response({"session_id": session.id, "saved": saved})


class MobileFinance(MobileAPIView):
    def get(self, request):
        students = students_for_mobile_user(request.user)
        invoices = Invoice.objects.filter(student__in=students).select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments")[:100]
        payments = Payment.objects.filter(invoice__student__in=students).select_related("invoice", "invoice__student")[:100]
        return Response({"invoices": [invoice_json(inv) for inv in invoices], "payments": [payment_json(p) for p in payments]})


class MobileExams(MobileAPIView):
    def get(self, request):
        students = list(students_for_mobile_user(request.user))
        rows = []
        for student in students:
            offering_ids = Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True)
            papers = ExamPaper.objects.filter(offering_id__in=offering_ids, is_published=True).select_related("exam", "offering", "offering__course")[:100]
            rows.append({"student": serialize_student(student), "papers": [paper_json(p, student=student) for p in papers]})
        return Response({"students": rows})


class MobileCoursework(MobileAPIView):
    def get(self, request):
        students = list(students_for_mobile_user(request.user))
        teacher = teacher_for_user(request.user)
        if teacher:
            materials = LearningMaterial.objects.filter(Q(offering__teacher=teacher) | Q(created_by=request.user)).select_related("offering", "offering__course")[:100]
            assignments = Assignment.objects.filter(Q(offering__teacher=teacher) | Q(created_by=request.user)).select_related("offering", "offering__course")[:100]
            return Response({"materials": [{"id": m.id, "title": m.title, "type": m.type, "course": str(m.offering.course) if m.offering else "", "publish_at": m.publish_at} for m in materials], "assignments": [{"id": a.id, "title": a.title, "course": str(a.offering.course) if a.offering else "", "due_date": a.due_date} for a in assignments]})
        rows = []
        for student in students:
            materials = visible_materials_for_student(student)[:100]
            assignments = visible_assignments_for_student(student)[:100]
            submissions = {s.assignment_id: s for s in AssignmentSubmission.objects.filter(student=student, assignment__in=assignments)}
            rows.append({"student": serialize_student(student), "materials": [{"id": m.id, "title": m.title, "type": m.type, "video_url": m.video_url, "meeting_url": m.meeting_url, "publish_at": m.publish_at} for m in materials], "assignments": [{"id": a.id, "title": a.title, "due_date": a.due_date, "submitted": bool(submissions.get(a.id) and submissions[a.id].submitted_at)} for a in assignments]})
        return Response({"students": rows})


class MobileMessages(MobileAPIView):
    def get(self, request):
        conversations = Conversation.objects.filter(participants=request.user, is_archived=False).prefetch_related("messages")[:50]
        announcements = Announcement.objects.filter(is_active=True).filter(Q(audience=Announcement.ALL) | Q(audience__in=user_roles(request.user)))[:50]
        return Response({"conversations": [{"id": c.id, "uuid": str(c.uuid), "subject": c.subject, "unread_count": c.get_unread_count(request.user), "updated_at": c.updated_at} for c in conversations], "announcements": [{"id": a.id, "title": a.title, "body": a.body, "is_urgent": a.is_urgent, "created_at": a.created_at} for a in announcements]})


class MobileTransport(MobileAPIView):
    def get(self, request):
        students = students_for_mobile_user(request.user)
        assignments = StudentTransportAssignment.objects.filter(student__in=students, is_active=True).select_related("student", "route", "route__vehicle", "route__driver", "stop")
        return Response({"assignments": [{"id": a.id, "student": serialize_student(a.student), "route": a.route.name, "route_code": a.route.code, "vehicle": str(a.route.vehicle or ""), "driver": str(a.route.driver or ""), "stop": str(a.stop or ""), "service_type": a.service_type, "monthly_fee": a.monthly_fee} for a in assignments]})


class MobileDeviceRegister(MobileAPIView):
    def post(self, request):
        platform = (request.data.get("platform") or MobileDevice.ANDROID).upper()
        device_id = request.data.get("device_id") or ""
        obj, _ = MobileDevice.objects.update_or_create(user=request.user, platform=platform, device_id=device_id, defaults={"push_token": request.data.get("push_token") or "", "app_version": request.data.get("app_version") or "", "is_active": True, "last_seen_at": timezone.now()})
        return Response({"id": obj.id, "platform": obj.platform, "device_id": obj.device_id, "registered": True})


class MobileDocs(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        base = "/api/v1/mobile/"
        return Response({"name": "EduManage Mobile API", "auth": {"token": "/api/v1/auth/token/", "refresh": "/api/v1/auth/token/refresh/", "header": "Authorization: Bearer <access>"}, "tenant": str(getattr(request, "tenant", "")), "endpoints": [base + p for p in ["me/", "dashboard/", "students/", "teachers/", "parents/", "attendance/", "finance/", "exams/", "coursework/", "messages/", "transport/", "devices/register/"]]})
