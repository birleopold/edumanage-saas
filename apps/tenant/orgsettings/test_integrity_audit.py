from django.test import TestCase

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile

from .integrity import audit_current_tenant, summarize_issues


class TenantIntegrityAuditTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        if self.campus is None:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                code="MAIN",
                is_active=True,
                is_default=True,
            )

    def _codes(self):
        return {issue.code for issue in audit_current_tenant()}

    def test_detects_cross_module_duplicates_and_conflicts(self):
        first_student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="STD-001",
            first_name="First",
            last_name="Learner",
        )
        StudentProfile.objects.create(
            campus=self.campus,
            student_id="std-001",
            first_name="Second",
            last_name="Learner",
        )

        ParentStudentLink.objects.create(
            parent=ParentProfile.objects.create(first_name="Parent", last_name="One"),
            student=first_student,
            relationship="Mother",
            is_primary=True,
        )
        ParentStudentLink.objects.create(
            parent=ParentProfile.objects.create(first_name="Parent", last_name="Two"),
            student=first_student,
            relationship="Father",
            is_primary=True,
        )

        year = AcademicYear.objects.create(name="2026")
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1)
        class_group = ClassGroup.objects.create(campus=self.campus, name="Primary One")
        course = Course.objects.create(name="Mathematics")
        CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
        )
        CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
        )

        codes = self._codes()

        self.assertIn("DUPLICATE_STUDENT_ID", codes)
        self.assertIn("MULTIPLE_PRIMARY_GUARDIANS", codes)
        self.assertIn("DUPLICATE_COURSE_OFFERING", codes)

    def test_summary_counts_severity_types(self):
        StudentProfile.objects.create(
            campus=self.campus,
            student_id="STD-002",
            first_name="First",
            last_name="Learner",
        )
        StudentProfile.objects.create(
            campus=self.campus,
            student_id="STD-002",
            first_name="Second",
            last_name="Learner",
        )

        summary = summarize_issues(audit_current_tenant())

        self.assertGreaterEqual(summary["ERROR"], 1)
