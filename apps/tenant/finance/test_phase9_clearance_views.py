from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    Level,
    Program,
    Stream,
)
from apps.tenant.exams.models import Exam, ExamPaper
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, UserRole

from .clearance_models import ClearanceOverride, ClearancePolicy
from .models import Invoice, InvoiceLine, Payment


class Phase9ClearanceViewTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Phase 9 View School")
        self.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.year = AcademicYear.objects.create(name="2030", is_current=True)
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1, is_current=True)
        level = Level.objects.create(name="Senior Five", order=5)
        program = Program.objects.create(name="Advanced Level", code="A-LVL")
        class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Five",
            level=level,
            program=program,
        )
        stream = Stream.objects.create(class_group=class_group, name="A")
        self.student_user = get_user_model().objects.create_user(
            username="phase9student",
            password="test-password",
        )
        student_role, _ = Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        UserRole.objects.create(user=self.student_user, role=student_role, campus=self.campus)
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            campus=self.campus,
            stream=stream,
            student_id="P9-VIEW",
            first_name="Amina",
            last_name="Learner",
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            academic_year=self.year,
            academic_term=self.term,
            reference="VIEW-T1",
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Tuition",
            quantity=1,
            unit_amount=Decimal("1000.00"),
        )
        Payment.objects.create(invoice=self.invoice, amount=Decimal("100.00"), method=Payment.CASH)
        self.superuser = get_user_model().objects.create_superuser(
            username="phase9admin",
            email="phase9admin@example.com",
            password="test-password",
        )

    def add_policy(self, access_type, **kwargs):
        data = {
            "code": f"POL-{access_type}",
            "name": f"Policy {access_type}",
            "access_type": access_type,
            "academic_term": self.term,
            "rule_type": ClearancePolicy.FULL_PAYMENT,
            "enforcement_mode": ClearancePolicy.BLOCK,
            "allow_when_no_invoice": True,
            "is_active": True,
        }
        data.update(kwargs)
        return ClearancePolicy.objects.create(**data)

    def test_student_assessment_results_are_blocked_without_changing_finance(self):
        self.add_policy(ClearancePolicy.ASSESSMENT_RESULTS)
        self.client.force_login(self.student_user)
        invoice_count = Invoice.objects.count()
        payment_count = Payment.objects.count()

        response = self.client.get(reverse("student_results_home"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Finance clearance", status_code=403)
        self.assertEqual(Invoice.objects.count(), invoice_count)
        self.assertEqual(Payment.objects.count(), payment_count)

    def test_advisory_policy_keeps_student_results_available(self):
        self.add_policy(
            ClearancePolicy.ASSESSMENT_RESULTS,
            enforcement_mode=ClearancePolicy.ADVISORY,
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("student_results_home"))
        self.assertEqual(response.status_code, 200)

    def test_valid_override_reopens_student_results(self):
        policy = self.add_policy(ClearancePolicy.ASSESSMENT_RESULTS)
        ClearanceOverride.objects.create(
            student=self.student,
            policy=policy,
            access_type=ClearancePolicy.ASSESSMENT_RESULTS,
            academic_term=self.term,
            reason="Approved payment-plan exception",
            approved_by=self.superuser,
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("student_results_home"))
        self.assertEqual(response.status_code, 200)

    def test_online_exam_start_uses_same_clearance_service(self):
        course = Course.objects.create(name="Mathematics", code="MATH")
        offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=self.term,
            class_group=self.student.stream.class_group,
        )
        Enrollment.objects.create(student=self.student, offering=offering, status=Enrollment.ACTIVE)
        exam = Exam.objects.create(name="Mock", term=self.term, exam_mode=Exam.ONLINE)
        paper = ExamPaper.objects.create(
            exam=exam,
            offering=offering,
            duration_minutes=60,
            is_published=True,
        )
        self.add_policy(ClearancePolicy.ONLINE_EXAM)
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("student_exam_start", args=[paper.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.student.exam_attempts.exists())

    def test_full_administrator_can_manage_policies_and_run_check(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin_finance_clearance_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exam and results access")

        response = self.client.post(
            reverse("admin_finance_clearance_learner_check"),
            {
                "student": self.student.pk,
                "access_type": ClearancePolicy.ASSESSMENT_RESULTS,
                "academic_term": self.term.pk,
                "record_decision": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No active policy matched")

    def test_campus_administrator_cannot_manage_global_clearance_rules(self):
        campus_role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        campus_user = get_user_model().objects.create_user(
            username="phase9campus",
            password="test-password",
        )
        UserRole.objects.create(user=campus_user, role=campus_role, campus=self.campus)
        self.client.force_login(campus_user)
        self.assertEqual(self.client.get(reverse("admin_finance_clearance_dashboard")).status_code, 403)
