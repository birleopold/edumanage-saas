from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import AcademicYear, ClassGroup, Level, Program, ProgrammePathway, Stream, SubjectCombination
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import LearnerSubjectCombination, MealAttendance, MealService, ReportTemplate, StudentProperty, VerifiablePermit, VisitationWindow, VisitorRecord


class InstitutionalOperationsTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Institutional School")
        self.campus = Campus.objects.create(organization=self.organization, name="Main Campus", code="MAIN", is_default=True, is_active=True)
        self.other_campus = Campus.objects.create(organization=self.organization, name="Other Campus", code="OTHER", is_active=True)
        self.level = Level.objects.create(name="Senior Five", order=5)
        self.program = Program.objects.create(name="Advanced Secondary", code="ADV")
        self.class_group = ClassGroup.objects.create(campus=self.campus, name="Senior Five", level=self.level, program=self.program)
        self.stream = Stream.objects.create(class_group=self.class_group, name="A")
        self.student = StudentProfile.objects.create(campus=self.campus, stream=self.stream, student_id="INST-001", first_name="Amina", last_name="Learner")
        self.other_student = StudentProfile.objects.create(campus=self.other_campus, student_id="INST-002", first_name="Other", last_name="Learner")
        self.admin = User.objects.create_superuser(username="institution-admin", email="admin@example.com", password="test-pass-123")
        self.client.login(username="institution-admin", password="test-pass-123")

    def test_dashboard_and_accessible_table_render(self):
        response = self.client.get(reverse("institutional_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Institutional Operations")
        list_response = self.client.get(reverse("institutional_resource_list", args=["permits"]))
        self.assertContains(list_response, '<caption class="sr-only">', html=False)
        self.assertContains(list_response, 'scope="col"', html=False)

    def test_report_template_rejects_unknown_section(self):
        template = ReportTemplate(name="Invalid", sections=["identity", "unknown"])
        with self.assertRaises(ValidationError):
            template.full_clean()

    def test_verification_page_reports_live_validity(self):
        permit = VerifiablePermit.objects.create(
            permit_type=VerifiablePermit.CLEARANCE,
            student=self.student,
            title="Assessment Clearance Permit",
            reference="CLR-INST-001",
            valid_until=timezone.now() + timedelta(days=3),
            approved_by=self.admin,
        )
        response = self.client.get(reverse("institutional_verify", args=[permit.verification_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valid institutional document")
        permit.status = VerifiablePermit.REVOKED
        permit.save(update_fields=["status"])
        response = self.client.get(reverse("institutional_verify", args=[permit.verification_token]))
        self.assertContains(response, "Document is not valid")

    def test_parent_cannot_open_unlinked_learner_records(self):
        parent_user = User.objects.create_user(username="institution-parent", password="test-pass-123")
        parent_role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
        UserRole.objects.create(user=parent_user, role=parent_role)
        parent = ParentProfile.objects.create(user=parent_user, first_name="Pat", last_name="Guardian")
        ParentStudentLink.objects.create(parent=parent, student=self.student, relationship="Mother", is_primary=True)
        self.client.logout()
        self.client.login(username="institution-parent", password="test-pass-123")
        own = self.client.get(reverse("institutional_student_records", args=[self.student.pk]))
        other = self.client.get(reverse("institutional_student_records", args=[self.other_student.pk]))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)

    def test_meal_attendance_enforces_campus_boundary(self):
        service = MealService.objects.create(campus=self.campus, meal=MealService.LUNCH)
        entry = MealAttendance(service=service, student=self.other_student)
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_visitor_window_enforces_campus_boundary(self):
        window = VisitationWindow.objects.create(
            campus=self.campus,
            name="Term visitation",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=5),
        )
        visitor = VisitorRecord(
            visitation_window=window,
            student=self.other_student,
            visitor_name="Visitor",
            identity_type="National ID",
            identity_number="ID-001",
            relationship="Guardian",
        )
        with self.assertRaises(ValidationError):
            visitor.full_clean()

    def test_released_property_requires_release_time(self):
        item = StudentProperty(student=self.student, item_name="Suitcase", status=StudentProperty.RELEASED)
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_subject_combination_capacity_is_enforced(self):
        year = AcademicYear.objects.create(name="2030")
        pathway = ProgrammePathway.objects.create(code="ADV-PATH", name="Advanced Pathway", program=self.program, campus=self.campus)
        combination = SubjectCombination.objects.create(code="PCM", name="Physics Chemistry Mathematics", pathway=pathway, level=self.level, settings={"capacity": 1})
        LearnerSubjectCombination.objects.create(student=self.student, combination=combination, academic_year=year)
        second = StudentProfile.objects.create(campus=self.campus, stream=self.stream, student_id="INST-003", first_name="Second", last_name="Learner")
        registration = LearnerSubjectCombination(student=second, combination=combination, academic_year=year)
        with self.assertRaises(ValidationError):
            registration.full_clean()
