from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.coursework.models import Assignment
from apps.tenant.discipline.models import Incident
from apps.tenant.finance.models import FeeItem, Invoice, InvoiceLine
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User

from .risk_radar import build_student_risk_radar


class StudentRiskRadarTests(TestCase):
    def setUp(self):
        self.admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin"})
        self.admin = User.objects.create_user(username="risk_admin", password="test-pass-123")
        self.admin.roles.add(self.admin_role)

        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        year = AcademicYear.objects.create(name="2026-RISK", is_current=True)
        self.term = AcademicTerm.objects.create(year=year, name="Term 1", order=1, is_current=True)
        class_group = ClassGroup.objects.create(name="Risk Class", campus=self.campus)
        stream = Stream.objects.create(class_group=class_group, name="A")
        course = Course.objects.create(name="Risk Math")
        teacher = TeacherProfile.objects.create(first_name="Risk", last_name="Teacher", campus=self.campus)
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=self.term,
            class_group=class_group,
            teacher=teacher,
        )
        self.student = StudentProfile.objects.create(
            first_name="Ada",
            last_name="Risk",
            campus=self.campus,
            stream=stream,
            student_id="RISK-001",
        )
        Enrollment.objects.create(offering=self.offering, student=self.student, campus=self.campus)

    def test_build_student_risk_radar_combines_school_signals(self):
        today = timezone.localdate()
        for offset in range(4):
            session = AttendanceSession.objects.create(offering=self.offering, date=today - timedelta(days=offset))
            AttendanceEntry.objects.create(session=session, student=self.student, status=AttendanceEntry.ABSENT)

        fee_item = FeeItem.objects.create(code="RISK-FEE", name="Risk Fee", amount=Decimal("50000"))
        invoice = Invoice.objects.create(student=self.student, academic_year=self.term.year, academic_term=self.term)
        InvoiceLine.objects.create(invoice=invoice, fee_item=fee_item, description="Tuition", quantity=1, unit_amount=Decimal("50000"))

        assessment = Assessment.objects.create(offering=self.offering, name="Midterm", max_score=Decimal("40"))
        AssessmentScore.objects.create(assessment=assessment, student=self.student, score=Decimal("18"))

        Assignment.objects.create(
            title="Missing work",
            offering=self.offering,
            stream=self.student.stream,
            due_date=timezone.now() - timedelta(days=2),
            is_active=True,
        )
        Incident.objects.create(student=self.student, title="Risk incident", status=Incident.OPEN)

        rows = build_student_risk_radar()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.student, self.student)
        self.assertEqual(row.level, "CRITICAL")
        self.assertEqual(row.attendance_rate, 0)
        self.assertEqual(row.missing_coursework, 1)
        self.assertEqual(row.discipline_count, 1)
        self.assertEqual(row.assessment_average, Decimal("45.00"))
        self.assertIn("attendance_low", {signal.key for signal in row.signals})
        self.assertIn("fees", {signal.key for signal in row.signals})

    def test_admin_risk_radar_page_renders_rows(self):
        session = AttendanceSession.objects.create(offering=self.offering, date=timezone.localdate())
        AttendanceEntry.objects.create(session=session, student=self.student, status=AttendanceEntry.ABSENT)

        self.client.login(username="risk_admin", password="test-pass-123")
        response = self.client.get(reverse("admin_analytics_risk_radar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Risk Radar")
        self.assertContains(response, "Risk Ada")
        self.assertContains(response, "Attendance drop")
