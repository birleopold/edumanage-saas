from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    Course,
    CourseOffering,
    Enrollment,
)
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .forms import AssessmentForm
from .models import Assessment, AssessmentScore, AssessmentType
from .policy_models import AssessmentPolicy, AssessmentScorePolicy
from .policy_services import (
    assessment_policy_readiness,
    effective_score,
    normalize_score_for_status,
)


class AssessmentPolicyTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Policy Test School")
        self.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        self.teacher = TeacherProfile.objects.create(
            campus=self.campus,
            first_name="Ada",
            last_name="Teacher",
        )
        year = AcademicYear.objects.create(name="2026")
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1)
        self.course = Course.objects.create(name="Mathematics", code="MATH")
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=term,
            teacher=self.teacher,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="ST-001",
            first_name="Learner",
            last_name="One",
        )
        Enrollment.objects.create(
            campus=self.campus,
            offering=self.offering,
            student=self.student,
        )
        self.numeric_type = AssessmentType.objects.create(
            code="TEST-POLICY",
            name="Policy Test",
            kind=AssessmentType.CONTINUOUS,
        )
        self.competency_type = AssessmentType.objects.create(
            code="COMP-POLICY",
            name="Competency Policy",
            kind=AssessmentType.COMPETENCY,
        )

    def create_assessment(self, **overrides):
        values = {
            "offering": self.offering,
            "name": "Test 1",
            "assessment_type": self.numeric_type,
            "max_score": Decimal("100"),
        }
        values.update(overrides)
        return Assessment.objects.create(**values)

    def test_new_assessment_receives_explicit_policy(self):
        assessment = self.create_assessment()

        self.assertTrue(hasattr(assessment, "policy"))
        self.assertEqual(assessment.policy.grading_mode, AssessmentPolicy.NUMERIC)
        self.assertEqual(assessment.policy.responsible_teacher, self.teacher)
        self.assertTrue(assessment.policy.show_on_report)

    def test_competency_type_defaults_to_competency_mode(self):
        assessment = self.create_assessment(
            name="Competency Task",
            assessment_type=self.competency_type,
        )

        self.assertEqual(
            assessment.policy.grading_mode,
            AssessmentPolicy.COMPETENCY,
        )

    def test_deferred_policy_requires_makeup_permission(self):
        assessment = self.create_assessment()
        policy = assessment.policy
        policy.absence_policy = AssessmentPolicy.DEFERRED
        policy.allow_makeup = False

        with self.assertRaises(ValidationError) as error:
            policy.full_clean()

        self.assertIn("allow_makeup", error.exception.message_dict)

    def test_zero_absence_policy_produces_effective_zero(self):
        assessment = self.create_assessment()
        policy = assessment.policy
        policy.absence_policy = AssessmentPolicy.ZERO
        policy.save(update_fields=["absence_policy", "updated_at"])
        score = AssessmentScore.objects.create(
            assessment=assessment,
            student=self.student,
            score=None,
        )
        score.policy.attendance_status = AssessmentScorePolicy.ABSENT
        score.policy.full_clean()
        score.policy.save(update_fields=["attendance_status", "updated_at"])

        self.assertEqual(effective_score(assessment, score), Decimal("0"))
        normalized, error = normalize_score_for_status(
            assessment,
            None,
            AssessmentScorePolicy.ABSENT,
        )
        self.assertIsNone(error)
        self.assertEqual(normalized, Decimal("0"))

    def test_competency_present_learner_requires_rating(self):
        assessment = self.create_assessment(
            name="Competency Task",
            assessment_type=self.competency_type,
        )
        score = AssessmentScore.objects.create(
            assessment=assessment,
            student=self.student,
            score=None,
        )
        score.policy.attendance_status = AssessmentScorePolicy.PRESENT
        score.policy.competency_rating = AssessmentScorePolicy.NOT_ASSESSED

        with self.assertRaises(ValidationError) as error:
            score.policy.full_clean()

        self.assertIn("competency_rating", error.exception.message_dict)

    def test_assessment_form_persists_policy_fields(self):
        assessment = self.create_assessment()
        form = AssessmentForm(
            data={
                "offering": self.offering.pk,
                "name": assessment.name,
                "assessment_type": self.numeric_type.pk,
                "weighting_component": "",
                "max_score": "100",
                "weight": "",
                "date": "",
                "grading_mode": AssessmentPolicy.MIXED,
                "absence_policy": AssessmentPolicy.MAKEUP_REQUIRED,
                "show_on_report": "on",
                "allow_makeup": "on",
                "responsible_teacher": self.teacher.pk,
                "competency_framework_key": "NCDC-CBC",
                "makeup_for": "",
                "deferred_until": "",
                "is_published": "",
            },
            instance=assessment,
            offerings=CourseOffering.objects.filter(pk=self.offering.pk),
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        form.save()
        assessment.policy.refresh_from_db()
        self.assertEqual(assessment.policy.grading_mode, AssessmentPolicy.MIXED)
        self.assertEqual(
            assessment.policy.absence_policy,
            AssessmentPolicy.MAKEUP_REQUIRED,
        )
        self.assertEqual(
            assessment.policy.competency_framework_key,
            "NCDC-CBC",
        )

    def test_readiness_reports_complete_policy_records(self):
        assessment = self.create_assessment()
        AssessmentScore.objects.create(
            assessment=assessment,
            student=self.student,
            score=Decimal("70"),
        )

        readiness = assessment_policy_readiness()

        self.assertEqual(readiness["missing_assessment_policy_count"], 0)
        self.assertEqual(readiness["missing_score_policy_count"], 0)
        self.assertEqual(readiness["invalid_assessment_policy_count"], 0)
