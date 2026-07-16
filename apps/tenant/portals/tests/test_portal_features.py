import re
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth.hashers import identify_hasher
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    Stream,
)
from apps.tenant.admissions.models import Applicant
from apps.tenant.announcements.models import Announcement
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.coursework.models import Assignment, AssignmentSubmission
from apps.tenant.discipline.models import Incident
from apps.tenant.documents.models import Document
from apps.tenant.admissions.pdf_letter import generate_admission_letter_pdf
from apps.tenant.assessments.parent_session import PIN_SESSION_KEY
from apps.tenant.audit.models import BackupJob
from apps.tenant.finance.integration_models import IntegrationProviderConfig
from apps.tenant.finance.models import FeeItem, Invoice, InvoiceLine, Payment
from apps.tenant.grievances.models import Grievance
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.hostels.models import Bed, BedAllocation, Hostel, HostelRoom
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.experience_services import build_school_health_score
from apps.tenant.portals.models import WebPushSubscription
from apps.tenant.students.models import StudentProfile
from apps.tenant.timetable.models import Period, TimetableEntry
from apps.tenant.finance.pdf_receipt import generate_payment_receipt_pdf
from apps.tenant.students.pdf_id_card import generate_student_id_card_pdf
from apps.tenant.users.models import Role, User, UserRole


class AdmissionLetterPdfTests(TestCase):
    def test_generates_pdf_bytes(self):
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        student = StudentProfile.objects.create(
            first_name="Ada",
            last_name="Applicant",
            campus=campus,
            student_id="ADM-001",
        )
        applicant = Applicant.objects.create(
            first_name="Ada",
            last_name="Applicant",
            campus=campus,
            status=Applicant.ADMITTED,
            created_student=student,
        )
        buf = generate_admission_letter_pdf(
            applicant=applicant,
            student=student,
            org=org,
            issued_by="Test Admin",
        )
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))


class StudentIdCardPdfTests(TestCase):
    def test_generates_pdf_bytes(self):
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        student = StudentProfile.objects.create(
            first_name="Ida",
            last_name="Card",
            campus=campus,
            student_id="ID-77",
        )
        buf = generate_student_id_card_pdf(student=student, org=org)
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))


class StudentIdCardSelfViewTests(TestCase):
    def setUp(self):
        self.role_student, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        self.user = User.objects.create_user(username="stu_id_self", password="test-pass-123")
        self.user.roles.add(self.role_student)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            user=self.user,
            first_name="Self",
            last_name="Card",
            campus=campus,
            student_id="SELF-ID-1",
        )

    def test_returns_pdf(self):
        self.client.login(username="stu_id_self", password="test-pass-123")
        resp = self.client.get(reverse("student_id_card_self"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))


class AdmissionLetterAdminPdfViewTests(TestCase):
    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.user = User.objects.create_user(username="adm_letter", password="test-pass-123")
        self.user.roles.add(self.role_admin)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        student = StudentProfile.objects.create(
            first_name="Let",
            last_name="Ter",
            campus=campus,
            student_id="LET-1",
        )
        self.applicant = Applicant.objects.create(
            first_name="Let",
            last_name="Ter",
            campus=campus,
            status=Applicant.ADMITTED,
            created_student=student,
        )

    def test_returns_pdf(self):
        self.client.login(username="adm_letter", password="test-pass-123")
        url = reverse("admin_admissions_applicant_letter_pdf", kwargs={"pk": self.applicant.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))


class AdminStudentIdCardPdfViewTests(TestCase):
    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.user = User.objects.create_user(username="adm_stu_id", password="test-pass-123")
        self.user.roles.add(self.role_admin)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            first_name="Adm",
            last_name="Student",
            campus=campus,
            student_id="ADM-STU-1",
        )

    def test_returns_pdf(self):
        self.client.login(username="adm_stu_id", password="test-pass-123")
        url = reverse("admin_students_id_card_pdf", kwargs={"pk": self.student.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))


class PaymentReceiptPdfTests(TestCase):
    def test_generates_pdf_bytes(self):
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        student = StudentProfile.objects.create(
            first_name="Sam",
            last_name="Student",
            campus=campus,
        )
        invoice = Invoice.objects.create(student=student, reference="T-INV-1")
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal("50000"),
            method=Payment.CASH,
        )
        buf = generate_payment_receipt_pdf(payment=payment, org=org, student_label=str(student))
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))


class ParentResultsPinSecurityViewTests(TestCase):
    def setUp(self):
        self.role_parent, _ = Role.objects.get_or_create(
            code=Role.PARENT,
            defaults={"name": "Parent"},
        )
        self.user = User.objects.create_user(username="parent_pin_user", password="test-pass-123")
        self.user.roles.add(self.role_parent)
        self.parent = ParentProfile.objects.create(
            user=self.user,
            first_name="Pat",
            last_name="Parent",
        )

    def test_set_pin_updates_profile(self):
        self.client.login(username="parent_pin_user", password="test-pass-123")
        url = reverse("parent_results_pin_security")
        resp = self.client.post(
            url,
            {"new_pin": "9876", "confirm_pin": "9876", "clear_pin": False},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.results_access_pin_hash)
        identify_hasher(self.parent.results_access_pin_hash)

    def test_session_unlock_cleared_after_pin_change(self):
        session = self.client.session
        session[PIN_SESSION_KEY] = {"parent_id": self.parent.pk, "expires_at": 9999999999.0}
        session.save()
        self.client.login(username="parent_pin_user", password="test-pass-123")
        self.client.post(
            reverse("parent_results_pin_security"),
            {"new_pin": "1111", "confirm_pin": "1111", "clear_pin": False},
        )
        self.assertNotIn(PIN_SESSION_KEY, self.client.session)


class StudentPaymentReceiptViewTests(TestCase):
    def setUp(self):
        self.role_student, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        self.user = User.objects.create_user(username="stu_receipt", password="test-pass-123")
        self.user.roles.add(self.role_student)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            user=self.user,
            first_name="R",
            last_name="Student",
            campus=campus,
        )
        self.invoice = Invoice.objects.create(student=self.student, reference="R-1")
        self.payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("100"),
            method=Payment.BANK,
        )

    def test_receipt_returns_pdf(self):
        self.client.login(username="stu_receipt", password="test-pass-123")
        url = reverse(
            "student_payment_receipt_pdf",
            kwargs={"pk": self.invoice.pk, "payment_id": self.payment.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))


class AdminHomeCampusScopeTests(TestCase):
    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.role_campus, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        org = get_or_create_organization()
        self.main = Campus.objects.filter(organization=org, is_default=True).first()
        self.other = Campus.objects.create(organization=org, name="Other Campus", is_active=True)
        StudentProfile.objects.create(
            first_name="On",
            last_name="Main",
            campus=self.main,
        )
        StudentProfile.objects.create(
            first_name="On",
            last_name="Other",
            campus=self.other,
        )

    def test_global_admin_sees_all_students(self):
        user = User.objects.create_user(username="global_admin", password="x")
        user.roles.add(self.role_admin)
        self.client.login(username="global_admin", password="x")
        resp = self.client.get(reverse("admin_home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["students_total"], 2)
        self.assertIn("admin_operations", resp.context)
        self.assertIn("school_health", resp.context)
        self.assertContains(resp, "Admin operations workflow")
        self.assertContains(resp, "Fast Search")
        self.assertContains(resp, "Bulk Actions")
        self.assertContains(resp, "Exports")
        self.assertContains(resp, "Audit Trails")
        self.assertContains(resp, "Dashboard Drill-downs")
        self.assertContains(resp, reverse("admin_global_search"))
        self.assertContains(resp, reverse("admin_students_bulk_import"))
        self.assertContains(resp, reverse("admin_enrollment_bulk"))
        self.assertContains(resp, reverse("admin_invoices_bulk_create"))
        self.assertContains(resp, reverse("audit_export_center"))
        self.assertContains(resp, reverse("admin_students_export_csv"))
        self.assertContains(resp, reverse("admin_invoices_export_csv"))
        self.assertContains(resp, reverse("admin_reports_overview_csv"))
        self.assertContains(resp, reverse("audit_activity_timeline"))
        self.assertContains(resp, reverse("audit_dashboard"))
        self.assertContains(resp, reverse("admin_reports_overview"))
        self.assertContains(resp, "Health Score")
        self.assertContains(resp, reverse("admin_school_health_score"))
        self.assertContains(resp, reverse("admin_analytics_risk_radar"))
        self.assertContains(resp, reverse("admin_sickbay_dashboard"))
        self.assertContains(resp, "Parent Digests")

    def test_campus_admin_sees_only_their_campus_students(self):
        user = User.objects.create_user(username="campus_only", password="x")
        user.roles.add(self.role_campus)
        UserRole.objects.create(user=user, role=self.role_campus, campus=self.main)
        self.client.login(username="campus_only", password="x")
        resp = self.client.get(reverse("admin_home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["students_total"], 1)


class FeatureEntryPointTests(TestCase):
    def setUp(self):
        self.role_teacher, _ = Role.objects.get_or_create(code=Role.TEACHER, defaults={"name": "Teacher"})
        self.role_student, _ = Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        self.role_parent, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()

    def test_teacher_home_mentions_offline_attendance_and_report_comments(self):
        user = User.objects.create_user(username="feature_teacher", password="test-pass-123")
        user.roles.add(self.role_teacher)
        teacher = TeacherProfile.objects.create(user=user, first_name="Feature", last_name="Teacher", campus=self.campus)
        year, _ = AcademicYear.objects.get_or_create(name="2099", defaults={"is_current": True})
        term, _ = AcademicTerm.objects.get_or_create(year=year, name="Term 1", defaults={"is_current": True, "order": 1})
        class_group = ClassGroup.objects.create(name="Feature Class", campus=self.campus)
        course = Course.objects.create(name="Daily Workflow")
        offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
            teacher=teacher,
        )
        student = StudentProfile.objects.create(first_name="Feature", last_name="Learner", campus=self.campus)
        Enrollment.objects.create(campus=self.campus, offering=offering, student=student)
        period = Period.objects.create(name="Period 1", order=1)
        today_code = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[timezone.localdate().weekday()]
        TimetableEntry.objects.create(offering=offering, weekday=today_code, period=period)
        AttendanceSession.objects.create(offering=offering, date=timezone.localdate(), taken_by=teacher)
        assignment = Assignment.objects.create(
            title="Mark me",
            offering=offering,
            campus=self.campus,
            class_group=class_group,
            created_by=user,
            publish_at=timezone.now(),
        )
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=student,
            submitted_at=timezone.now(),
        )
        Incident.objects.create(
            student=student,
            reported_by=teacher,
            title="Uniform concern",
            status=Incident.OPEN,
        )
        Announcement.objects.create(
            title="Staff briefing",
            body="Meet after class.",
            audience=Announcement.TEACHERS,
            is_active=True,
            is_urgent=True,
        )
        self.client.login(username="feature_teacher", password="test-pass-123")

        resp = self.client.get(reverse("teacher_home"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "work offline")
        self.assertContains(resp, "draft report comments")
        self.assertContains(resp, "Today&apos;s teacher workflow")
        self.assertContains(resp, reverse("teacher_timetable"))
        self.assertContains(resp, reverse("teacher_roll_call"))
        self.assertContains(resp, reverse("teacher_coursework_home"))
        self.assertContains(resp, reverse("teacher_incidents_report"))
        self.assertContains(resp, "lesson(s) scheduled today")
        self.assertContains(resp, "submission(s) awaiting marks")
        self.assertContains(resp, "open report(s) from you")
        self.assertContains(resp, "Staff briefing")

    def test_student_home_links_sickbay(self):
        user = User.objects.create_user(username="feature_student", password="test-pass-123")
        user.roles.add(self.role_student)
        StudentProfile.objects.create(user=user, first_name="Feature", last_name="Student", campus=self.campus)
        self.client.login(username="feature_student", password="test-pass-123")

        resp = self.client.get(reverse("student_home"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("student_sickbay_visits"))
        self.assertContains(resp, "Sickbay")

    def test_parent_home_links_digests_and_sickbay(self):
        user = User.objects.create_user(username="feature_parent", password="test-pass-123")
        user.roles.add(self.role_parent)
        parent = ParentProfile.objects.create(
            user=user,
            first_name="Feature",
            last_name="Parent",
            allow_sms_alerts=True,
            digest_enabled=True,
        )
        student = StudentProfile.objects.create(first_name="Feature", last_name="Child", campus=self.campus)
        ParentStudentLink.objects.create(parent=parent, student=student)
        year, _ = AcademicYear.objects.get_or_create(name="2100", defaults={"is_current": True})
        term, _ = AcademicTerm.objects.get_or_create(year=year, name="Term 1", defaults={"is_current": True, "order": 1})
        class_group = ClassGroup.objects.create(name="Parent Feature Class", campus=self.campus)
        course = Course.objects.create(name="Parent Workflow")
        teacher_user = User.objects.create_user(username="parent_feature_teacher", password="test-pass-123")
        teacher = TeacherProfile.objects.create(user=teacher_user, first_name="P", last_name="Teacher", campus=self.campus)
        offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
            teacher=teacher,
        )
        Enrollment.objects.create(campus=self.campus, offering=offering, student=student)
        session = AttendanceSession.objects.create(offering=offering, date=timezone.localdate(), taken_by=teacher)
        AttendanceEntry.objects.create(session=session, student=student, status=AttendanceEntry.PRESENT)
        assessment = Assessment.objects.create(offering=offering, name="Midterm", is_published=True)
        AssessmentScore.objects.create(assessment=assessment, student=student, score=Decimal("82"))
        invoice = Invoice.objects.create(student=student, academic_year=year, academic_term=term, reference="PF-001")
        fee_item = FeeItem.objects.create(code="PF-TUITION", name="Parent Feature Tuition", amount=Decimal("1000"))
        InvoiceLine.objects.create(invoice=invoice, fee_item=fee_item, description="Tuition", quantity=1, unit_amount=Decimal("1000"))
        Announcement.objects.create(
            title="Parent briefing",
            body="Bring report card questions.",
            audience=Announcement.PARENTS,
            is_active=True,
            is_urgent=True,
        )
        Document.objects.create(
            title="Parent Handbook",
            description="Daily family reference.",
            file=SimpleUploadedFile("parent-handbook.pdf", b"pdf"),
            audience=Document.PARENTS,
            is_active=True,
        )
        self.client.login(username="feature_parent", password="test-pass-123")

        resp = self.client.get(reverse("parent_home"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("parent_digest_history"))
        self.assertContains(resp, reverse("parent_sickbay_visits"))
        self.assertContains(resp, "Weekly Digests")
        self.assertContains(resp, "Today&apos;s family workflow")
        self.assertContains(resp, reverse("parent_invoices_list"))
        self.assertContains(resp, reverse("parent_attendance_home"))
        self.assertContains(resp, reverse("parent_results_home"))
        self.assertContains(resp, reverse("parent_announcements_list"))
        self.assertContains(resp, reverse("parent_documents_list"))
        self.assertContains(resp, reverse("parent_communication_preferences"))
        self.assertContains(resp, "invoice(s) with balance to review")
        self.assertContains(resp, "attendance record(s) available")
        self.assertContains(resp, "published result(s)")
        self.assertContains(resp, "Parent briefing")
        self.assertContains(resp, "Parent Handbook")


class ParentChildIdCardPdfViewTests(TestCase):
    def setUp(self):
        self.role_parent, _ = Role.objects.get_or_create(
            code=Role.PARENT,
            defaults={"name": "Parent"},
        )
        self.parent_user = User.objects.create_user(username="par_id_card", password="test-pass-123")
        self.parent_user.roles.add(self.role_parent)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            first_name="Kid",
            last_name="Test",
            campus=campus,
            student_id="K-1",
        )
        self.parent_profile = ParentProfile.objects.create(
            user=self.parent_user,
            first_name="P",
            last_name="Test",
        )
        ParentStudentLink.objects.create(parent=self.parent_profile, student=self.student)

    def test_returns_pdf_for_linked_child(self):
        self.client.login(username="par_id_card", password="test-pass-123")
        url = reverse("parent_child_id_card_pdf", kwargs={"student_pk": self.student.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))


class GlobalSearchViewTests(TestCase):
    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.user = User.objects.create_user(username="glob_search_adm", password="test-pass-123")
        self.user.roles.add(self.role_admin)

    def test_search_renders(self):
        self.client.login(username="glob_search_adm", password="test-pass-123")
        resp = self.client.get(reverse("admin_global_search"), {"q": "ab"})
        self.assertEqual(resp.status_code, 200)


class GlobalSearchResultsTests(TestCase):
    """Applicants, grievances, and fee items appear in global search HTML."""

    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.role_campus, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        self.admin = User.objects.create_user(username="gs_full_admin", password="test-pass-123")
        self.admin.roles.add(self.role_admin)
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org, is_default=True).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Campus GS",
            is_active=True,
        )
        self.grievance_submitter = User.objects.create_user(
            username="gs_griev_submitter",
            password="test-pass-123",
        )
        Applicant.objects.create(
            first_name="Xyglobapfn",
            last_name="Smith",
            campus=self.campus,
            email="xy@glob.test",
        )
        Grievance.objects.create(
            campus=self.campus,
            submitted_by=self.grievance_submitter,
            subject="Noise complaint Xyglobgri subj",
            body="Body text for search Xyglobgribody",
        )
        FeeItem.objects.create(code="XYGLOBFEE99", name="Annual stack fee", is_active=True)

    def test_admin_sees_applicant_grievance_and_fee_item(self):
        self.client.login(username="gs_full_admin", password="test-pass-123")
        resp = self.client.get(reverse("admin_global_search"), {"q": "Xyglob"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Smith")
        self.assertContains(resp, "Xyglobapfn")
        self.assertContains(resp, "Xyglobgri")
        self.assertContains(resp, "XYGLOBFEE99")
        self.assertContains(resp, "Annual stack fee")

    def test_campus_admin_does_not_see_applicant_from_other_campus(self):
        hidden = Applicant.objects.create(
            first_name="Other",
            last_name="Zuniqueother99",
            campus=self.other_campus,
        )
        campus_user = User.objects.create_user(username="gs_campus_only", password="test-pass-123")
        campus_user.roles.add(self.role_campus)
        UserRole.objects.create(user=campus_user, role=self.role_campus, campus=self.campus)
        self.client.login(username="gs_campus_only", password="test-pass-123")
        resp = self.client.get(reverse("admin_global_search"), {"q": "Zuniqueother99"})
        self.assertEqual(resp.status_code, 200)
        # Do not assert on the query string: it is echoed in the search <input value="…">.
        self.assertNotContains(
            resp,
            reverse("admin_admissions_applicant_detail", kwargs={"pk": hidden.pk}),
        )

    def test_campus_admin_sees_unassigned_campus_applicant(self):
        Applicant.objects.create(
            first_name="Unassigned",
            last_name="Znullcampus99",
            campus=None,
        )
        campus_user = User.objects.create_user(username="gs_campus_null", password="test-pass-123")
        campus_user.roles.add(self.role_campus)
        UserRole.objects.create(user=campus_user, role=self.role_campus, campus=self.campus)
        self.client.login(username="gs_campus_null", password="test-pass-123")
        resp = self.client.get(reverse("admin_global_search"), {"q": "Znullcampus99"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Znullcampus99")


class TeacherSearchViewTests(TestCase):
    def setUp(self):
        self.role_teacher, _ = Role.objects.get_or_create(
            code=Role.TEACHER,
            defaults={"name": "Teacher"},
        )
        self.user = User.objects.create_user(username="tsearch_teacher", password="test-pass-123")
        self.user.roles.add(self.role_teacher)
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org, is_default=True).first()
        self.teacher = TeacherProfile.objects.create(
            user=self.user,
            campus=self.campus,
            first_name="Tea",
            last_name="Search",
        )
        year = AcademicYear.objects.create(name="2026-TSY", is_current=False)
        term = AcademicTerm.objects.create(year=year, name="T1-TS", order=1, is_current=True)
        course = Course.objects.create(name="Math TeacherSearch")
        class_group = ClassGroup.objects.create(name="Form TS", campus=self.campus)
        stream = Stream.objects.create(
            class_group=class_group,
            name="A",
            class_teacher=self.teacher,
        )
        self.student = StudentProfile.objects.create(
            first_name="ZetaTsearch",
            last_name="Pupil",
            campus=self.campus,
            stream=stream,
            student_id="TS-PUP-1",
        )
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
            teacher=self.teacher,
        )
        Enrollment.objects.create(
            offering=self.offering,
            student=self.student,
            campus=self.campus,
            status=Enrollment.ACTIVE,
        )
        Grievance.objects.create(
            campus=self.campus,
            submitted_by=self.user,
            subject="Noise TS Grvxyz",
            body="Details for grievance search.",
        )

    def test_finds_taught_student_and_own_grievance(self):
        self.client.login(username="tsearch_teacher", password="test-pass-123")
        resp = self.client.get(reverse("teacher_global_search"), {"q": "ZetaTse"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ZetaTsearch")
        self.assertContains(resp, f"offering={self.offering.pk}")
        resp_g = self.client.get(reverse("teacher_global_search"), {"q": "Grvxyz"})
        self.assertEqual(resp_g.status_code, 200)
        self.assertContains(resp_g, "Grvxyz")

    def test_does_not_list_unrelated_student(self):
        other_stream = Stream.objects.create(
            class_group=ClassGroup.objects.create(name="Other TS", campus=self.campus),
            name="B",
        )
        StudentProfile.objects.create(
            first_name="ZetaTsearch",
            last_name="Stranger",
            campus=self.campus,
            stream=other_stream,
            student_id="TS-OTHER",
        )
        self.client.login(username="tsearch_teacher", password="test-pass-123")
        resp = self.client.get(reverse("teacher_global_search"), {"q": "Stranger"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "TS-OTHER")


class StudentSearchViewTests(TestCase):
    def setUp(self):
        self.role_student, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        self.user = User.objects.create_user(username="stu_search_user", password="test-pass-123")
        self.user.roles.add(self.role_student)
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org, is_default=True).first()
        self.student = StudentProfile.objects.create(
            user=self.user,
            first_name="Search",
            last_name="Student",
            campus=self.campus,
            student_id="STU-SRCH-1",
        )
        Announcement.objects.create(
            title="Unique Stu Announcexy",
            body="Body",
            audience=Announcement.STUDENTS,
            is_active=True,
        )
        Invoice.objects.create(student=self.student, reference="INV-STU-SRCH-99")

    def test_student_search_finds_matches(self):
        self.client.login(username="stu_search_user", password="test-pass-123")
        resp = self.client.get(reverse("student_global_search"), {"q": "Announcexy"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Announcexy")
        resp2 = self.client.get(reverse("student_global_search"), {"q": "INV-STU-SRCH"})
        self.assertContains(resp2, "INV-STU-SRCH-99")


class ParentSearchViewTests(TestCase):
    def setUp(self):
        self.role_parent, _ = Role.objects.get_or_create(
            code=Role.PARENT,
            defaults={"name": "Parent"},
        )
        self.user = User.objects.create_user(username="par_search_user", password="test-pass-123")
        self.user.roles.add(self.role_parent)
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org, is_default=True).first()
        self.parent_profile = ParentProfile.objects.create(
            user=self.user,
            first_name="Par",
            last_name="Search",
        )
        self.child = StudentProfile.objects.create(
            first_name="UniqueChildNm",
            last_name="Kid",
            campus=self.campus,
            student_id="PAR-CH-1",
        )
        ParentStudentLink.objects.create(parent=self.parent_profile, student=self.child)
        Announcement.objects.create(
            title="Unique Par Announcexy",
            body="Body",
            audience=Announcement.PARENTS,
            is_active=True,
        )
        Grievance.objects.create(
            campus=self.campus,
            submitted_by=self.user,
            subject="Parent grievance ParGrvxy",
            body="Text",
        )
        Invoice.objects.create(student=self.child, reference="INV-PAR-SRCH-88")
        Assignment.objects.create(
            title="ParSearchAsgXy title",
            instructions="",
            publish_at=timezone.now(),
            is_active=True,
        )

    def test_parent_search_finds_child_announcement_grievance_invoice_assignment(self):
        self.client.login(username="par_search_user", password="test-pass-123")
        r1 = self.client.get(reverse("parent_global_search"), {"q": "UniqueChild"})
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, "UniqueChildNm")
        r_ann = self.client.get(reverse("parent_global_search"), {"q": "Announcexy"})
        self.assertContains(r_ann, "Unique Par Announcexy")
        r2 = self.client.get(reverse("parent_global_search"), {"q": "ParGrvxy"})
        self.assertContains(r2, "ParGrvxy")
        r3 = self.client.get(reverse("parent_global_search"), {"q": "INV-PAR-SRCH"})
        self.assertContains(r3, "INV-PAR-SRCH-88")
        r4 = self.client.get(reverse("parent_global_search"), {"q": "ParSearchAsg"})
        self.assertEqual(r4.status_code, 200)
        self.assertContains(r4, "ParSearchAsgXy")


class ChartsOverviewApiTests(TestCase):
    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.user = User.objects.create_user(username="charts_api_adm", password="test-pass-123")
        self.user.roles.add(self.role_admin)

    def test_json(self):
        self.client.login(username="charts_api_adm", password="test-pass-123")
        resp = self.client.get(reverse("admin_analytics_api_charts_overview"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("students_by_campus", data)
        self.assertIn("summary", data)

    def test_charts_page(self):
        self.client.login(username="charts_api_adm", password="test-pass-123")
        resp = self.client.get(reverse("admin_analytics_charts"))
        self.assertEqual(resp.status_code, 200)


class ExperienceHubViewsTests(TestCase):
    """Staff Communication Hub, setup guide, and system status."""

    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.user = User.objects.create_user(username="ux_exp_hub", password="test-pass-123")
        self.user.roles.add(self.role_admin)

    def test_communication_center_renders(self):
        self.client.login(username="ux_exp_hub", password="test-pass-123")
        resp = self.client.get(reverse("admin_communication_center"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Communication Hub")

    def test_school_setup_guide_renders(self):
        self.client.login(username="ux_exp_hub", password="test-pass-123")
        resp = self.client.get(reverse("admin_school_setup_guide"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "checklist")

    def test_school_health_score_renders(self):
        self.client.login(username="ux_exp_hub", password="test-pass-123")
        resp = self.client.get(reverse("admin_school_health_score"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "School setup health score")

    def test_school_health_score_data_returns_json(self):
        self.client.login(username="ux_exp_hub", password="test-pass-123")
        resp = self.client.get(reverse("admin_school_health_score_data"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("percent", data)
        self.assertIn("items", data)
        self.assertIn("top_gaps", data)

    def test_school_health_score_reflects_ready_setup(self):
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        campus.is_active = True
        campus.is_default = True
        campus.save(update_fields=["is_active", "is_default"])

        year = AcademicYear.objects.create(name="2026", is_current=True)
        AcademicTerm.objects.create(year=year, name="Term 1", order=1, is_current=True)
        FeeItem.objects.create(code="TUITION", name="Tuition", amount=Decimal("500000"), is_active=True)

        for code, name in Role.CODE_CHOICES:
            Role.objects.get_or_create(code=code, defaults={"name": name})
        UserRole.objects.get_or_create(user=self.user, role=self.role_admin, campus=None)
        teacher_role = Role.objects.get(code=Role.TEACHER)
        teacher_user = User.objects.create_user(username="ux_exp_teacher", password="test-pass-123")
        UserRole.objects.create(user=teacher_user, role=teacher_role, campus=campus)

        WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/score",
            p256dh_key="key",
            auth_key="auth",
            is_active=True,
        )
        BackupJob.objects.create(
            requested_by=self.user,
            status=BackupJob.SUCCESS,
            finished_at=timezone.now(),
        )
        IntegrationProviderConfig.objects.create(
            name="MTN test",
            provider_type=IntegrationProviderConfig.MTN_MOMO,
            is_active=True,
            base_url="https://payments.example.test",
        )

        with self.settings(WEB_PUSH_PUBLIC_KEY="public-key", WEB_PUSH_PRIVATE_KEY="private-key"):
            health = build_school_health_score()

        self.assertEqual(health["percent"], 100)
        self.assertEqual(health["level"], "Ready")

    def test_school_health_score_prioritizes_largest_gaps(self):
        health = build_school_health_score()
        gap_points = [item["gap_points"] for item in health["top_gaps"]]
        self.assertEqual(gap_points, sorted(gap_points, reverse=True))

    def test_check_school_health_command_reports_score(self):
        out = StringIO()
        call_command("check_school_health", stdout=out)
        self.assertIn("School setup health:", out.getvalue())

    def test_check_school_health_command_can_enforce_threshold(self):
        with self.assertRaises(CommandError):
            call_command("check_school_health", min_percent=101, stdout=StringIO())

    def test_system_status_renders(self):
        self.client.login(username="ux_exp_hub", password="test-pass-123")
        resp = self.client.get(reverse("admin_system_status"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "System status")


class ParentCommunicationPreferencesViewTests(TestCase):
    def setUp(self):
        self.role_parent, _ = Role.objects.get_or_create(
            code=Role.PARENT,
            defaults={"name": "Parent"},
        )
        self.user = User.objects.create_user(username="par_comm_pref", password="test-pass-123")
        self.user.roles.add(self.role_parent)
        self.parent = ParentProfile.objects.create(
            user=self.user,
            first_name="Comm",
            last_name="Parent",
            allow_sms_alerts=True,
            allow_whatsapp_alerts=False,
        )

    def test_get_renders(self):
        self.client.login(username="par_comm_pref", password="test-pass-123")
        resp = self.client.get(reverse("parent_communication_preferences"))
        self.assertEqual(resp.status_code, 200)

    def test_post_updates_whatsapp_toggle(self):
        self.client.login(username="par_comm_pref", password="test-pass-123")
        resp = self.client.post(
            reverse("parent_communication_preferences"),
            {"allow_sms_alerts": "on", "allow_whatsapp_alerts": "on"},
        )
        self.assertEqual(resp.status_code, 302)
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.allow_whatsapp_alerts)
        self.assertIsNotNone(self.parent.communication_consent_updated_at)


class PublicStatusPageTests(TestCase):
    def test_json(self):
        resp = self.client.get(reverse("public_status"), {"format": "json"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "edumanage")
        self.assertIn("fee_messaging", data)
        self.assertEqual(resp.headers["Cache-Control"], "no-store")

    def test_html_renders(self):
        resp = self.client.get(reverse("public_status"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Service status")


class OperationalReadinessCommandTests(TestCase):
    def test_command_prints_release_gates(self):
        out = StringIO()
        call_command("check_operational_readiness", stdout=out)
        text = out.getvalue()

        self.assertIn("Operational readiness checklist", text)
        self.assertIn("python manage.py check", text)
        self.assertIn("Public health route", text)
        self.assertIn("External monitoring plan", text)

    def test_command_json_reports_manual_external_checks_without_failing_strict(self):
        out = StringIO()
        call_command("check_operational_readiness", "--json", "--strict", stdout=out)
        payload = json.loads(out.getvalue())

        self.assertTrue(payload["ok"])
        statuses = {item["status"] for item in payload["checks"]}
        self.assertIn("manual", statuses)
        self.assertIn("pass", statuses)

    def test_command_reports_backup_and_restore_evidence(self):
        BackupJob.objects.create(
            status=BackupJob.SUCCESS,
            file_path="s3://backups/nightly.sql.gz",
            checksum="abc123",
            finished_at=timezone.now(),
        )
        BackupJob.objects.create(
            status=BackupJob.RESTORE_TESTED,
            notes="Restored into staging and verified smoke tests.",
            finished_at=timezone.now(),
        )

        out = StringIO()
        call_command("check_operational_readiness", "--json", "--strict", stdout=out)
        payload = json.loads(out.getvalue())
        checks = {item["name"]: item for item in payload["checks"]}

        self.assertEqual(checks["Recent successful backup audit"]["status"], "pass")
        self.assertEqual(checks["Quarterly restore drill audit"]["status"], "pass")
        self.assertEqual(checks["External monitoring plan"]["status"], "pass")

    def test_record_backup_command_records_restore_drill(self):
        out = StringIO()
        call_command(
            "record_backup",
            "--status",
            BackupJob.RESTORE_TESTED,
            "--notes",
            "Quarterly restore drill completed.",
            stdout=out,
        )

        job = BackupJob.objects.get(status=BackupJob.RESTORE_TESTED)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)
        self.assertIn("Backup audit record created", out.getvalue())

    def test_command_strict_fails_when_production_settings_are_required_in_test_settings(self):
        with self.assertRaises(CommandError):
            call_command(
                "check_operational_readiness",
                "--strict",
                "--require-production-settings",
                stdout=StringIO(),
            )


class BulkImportPreviewFlowTests(TestCase):
    def setUp(self):
        self.role_admin, _ = Role.objects.get_or_create(
            code=Role.ADMIN,
            defaults={"name": "Admin"},
        )
        self.user = User.objects.create_user(username="bulk_import_adm", password="test-pass-123")
        self.user.roles.add(self.role_admin)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        if campus and not (campus.code or "").strip():
            campus.code = "MAIN"
            campus.save(update_fields=["code"])

    def test_preview_shows_valid_row(self):
        self.client.login(username="bulk_import_adm", password="test-pass-123")
        csv_content = b"first_name,last_name,email,campus_code\nZetaBulk,Child,z@example.com,MAIN\n"
        up = SimpleUploadedFile("students.csv", csv_content, content_type="text/csv")
        resp = self.client.post(
            reverse("admin_students_bulk_import"),
            {"action": "preview", "import_file": up},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ZetaBulk")
        m = re.search(r'name="preview_token" value="([^"]+)"', resp.content.decode())
        self.assertIsNotNone(m)
        token = m.group(1)
        conf = self.client.post(
            reverse("admin_students_bulk_import"),
            {"action": "confirm", "preview_token": token},
        )
        self.assertEqual(conf.status_code, 302)
        self.assertTrue(
            StudentProfile.objects.filter(first_name="ZetaBulk", last_name="Child").exists()
        )


class ParentHostelHomeViewTests(TestCase):
    def setUp(self):
        self.role_parent, _ = Role.objects.get_or_create(
            code=Role.PARENT,
            defaults={"name": "Parent"},
        )
        self.parent_user = User.objects.create_user(username="par_hostel", password="test-pass-123")
        self.parent_user.roles.add(self.role_parent)
        org = get_or_create_organization()
        campus = Campus.objects.filter(organization=org).first()
        self.student = StudentProfile.objects.create(
            first_name="H",
            last_name="Kid",
            campus=campus,
            student_id="H-1",
        )
        self.parent_profile = ParentProfile.objects.create(
            user=self.parent_user,
            first_name="H",
            last_name="Par",
        )
        ParentStudentLink.objects.create(parent=self.parent_profile, student=self.student)
        hostel = Hostel.objects.create(name="Hall A", code="A")
        room = HostelRoom.objects.create(hostel=hostel, name="101")
        bed = Bed.objects.create(room=room, label="1")
        BedAllocation.objects.create(bed=bed, student=self.student, status=BedAllocation.ACTIVE)

    def test_lists_allocations(self):
        self.client.login(username="par_hostel", password="test-pass-123")
        resp = self.client.get(reverse("parent_hostel_home"))
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.context["allocations"]), 1)
