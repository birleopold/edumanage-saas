from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from ..models import Assessment, AssessmentScore


class AssessmentAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Assessment Campus",
            is_active=True,
        )
        year = AcademicYear.objects.create(name="2026", is_current=True)
        self.term = AcademicTerm.objects.create(
            year=year,
            name="Term 1",
            order=1,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 5, 31),
            is_current=True,
        )
        self.course = Course.objects.create(name="Assessment Mathematics", is_active=True)
        self.class_group = ClassGroup.objects.create(name="Assessment Main", campus=self.campus, is_active=True)
        self.other_class_group = ClassGroup.objects.create(name="Assessment Other", campus=self.other_campus, is_active=True)
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=self.class_group,
        )
        self.other_offering = CourseOffering.objects.create(
            campus=self.other_campus,
            course=self.course,
            term=self.term,
            class_group=self.other_class_group,
        )
        self.assessment = Assessment.objects.create(
            offering=self.offering,
            name="Visible Quiz",
            max_score=Decimal("100"),
            date=date(2026, 3, 1),
        )
        self.hidden_assessment = Assessment.objects.create(
            offering=self.other_offering,
            name="Hidden Quiz",
            max_score=Decimal("100"),
            date=date(2026, 3, 1),
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Learner",
            student_id="AS-VISIBLE",
            campus=self.campus,
            is_active=True,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Learner",
            student_id="AS-HIDDEN",
            campus=self.other_campus,
            is_active=True,
        )
        Enrollment.objects.create(offering=self.offering, student=self.student, campus=self.campus)
        Enrollment.objects.create(offering=self.other_offering, student=self.hidden_student, campus=self.other_campus)

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="assessment_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_assessment_list_sees_own_campus_only(self):
        self.client.login(username="assessment_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_assessments_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Quiz")
        self.assertNotContains(response, "Hidden Quiz")

    def test_campus_admin_cannot_access_other_campus_assessment(self):
        self.client.login(username="assessment_campus_admin", password="test-pass-123")

        edit_response = self.client.get(reverse("admin_assessments_edit", kwargs={"pk": self.hidden_assessment.pk}))
        scores_response = self.client.get(reverse("admin_assessments_scores", kwargs={"pk": self.hidden_assessment.pk}))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(scores_response.status_code, 404)

    def test_campus_admin_cannot_create_assessment_for_other_campus_offering(self):
        self.client.login(username="assessment_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_assessments_create"),
            {
                "offering": self.other_offering.pk,
                "name": "Forged Quiz",
                "max_score": "100",
                "weight": "",
                "date": "2026-03-02",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Assessment.objects.filter(name="Forged Quiz").exists())

    def test_campus_admin_score_post_ignores_forged_student_ids(self):
        self.client.login(username="assessment_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_assessments_scores", kwargs={"pk": self.assessment.pk}),
            {
                "student_ids": [str(self.student.pk), str(self.hidden_student.pk)],
                f"score_{self.student.pk}": "88",
                f"score_{self.hidden_student.pk}": "99",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AssessmentScore.objects.filter(
                assessment=self.assessment,
                student=self.student,
                score=Decimal("88"),
            ).exists()
        )
        self.assertFalse(
            AssessmentScore.objects.filter(
                assessment=self.assessment,
                student=self.hidden_student,
            ).exists()
        )

    def test_campus_admin_tabulation_ignores_other_campus_offering(self):
        self.client.login(username="assessment_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_assessments_tabulation"), {"offering": self.other_offering.pk})

        self.assertEqual(response.status_code, 404)
