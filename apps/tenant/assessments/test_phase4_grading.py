from decimal import Decimal

from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    GradeRange,
    GradingScale,
    Level,
    Stream,
)
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .grading_results import build_report_card, score_result
from .grading_services import grading_framework_readiness, resolve_grading_profile
from .models import Assessment, AssessmentScore, GradingProfile, ReportRule


class Phase4GradingProfileTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        self.year = AcademicYear.objects.create(name="2026")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.level = Level.objects.create(name="Senior One", order=1)
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior One",
            level=self.level,
        )
        self.stream = Stream.objects.create(class_group=self.class_group, name="A")
        self.course = Course.objects.create(name="Mathematics", code="MATH", level=self.level, credits=3)
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=self.class_group,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="P4-001",
            first_name="Amina",
            last_name="Learner",
        )
        Enrollment.objects.create(campus=self.campus, offering=self.offering, student=self.student)
        self.scale = GradingScale.objects.create(name="Phase 4 Scale", is_default=True, is_active=True)
        GradeRange.objects.create(scale=self.scale, grade="A", min_score=80, max_score=100, remark="Excellent", order=1)
        GradeRange.objects.create(scale=self.scale, grade="B", min_score=70, max_score=79.99, remark="Very good", order=2)
        GradeRange.objects.create(scale=self.scale, grade="C", min_score=60, max_score=69.99, remark="Good", order=3)
        GradeRange.objects.create(scale=self.scale, grade="D", min_score=50, max_score=59.99, remark="Fair", order=4)
        GradeRange.objects.create(scale=self.scale, grade="F", min_score=0, max_score=49.99, remark="Needs support", order=5)

    def _profile(self, code="DEFAULT-GRADING", **overrides):
        values = {
            "code": code,
            "name": code.replace("-", " ").title(),
            "grading_scale": self.scale,
            "is_default": code == "DEFAULT-GRADING",
            "is_active": True,
        }
        values.update(overrides)
        profile = GradingProfile.objects.create(**values)
        ReportRule.objects.create(grading_profile=profile, show_promotion_status=True)
        return profile

    def test_more_specific_profile_wins_deterministically(self):
        self._profile()
        specific_scale = GradingScale.objects.create(name="Senior One Scale", is_active=True)
        GradeRange.objects.create(scale=specific_scale, grade="DIST", min_score=75, max_score=100, remark="Distinction")
        GradeRange.objects.create(scale=specific_scale, grade="PASS", min_score=0, max_score=74.99, remark="Pass")
        specific = self._profile(
            "S1-GRADING",
            grading_scale=specific_scale,
            level=self.level,
            priority=10,
        )

        self.assertEqual(resolve_grading_profile(self.offering), specific)

    def test_score_result_uses_matching_existing_grading_scale(self):
        profile = self._profile(level=self.level)
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="End of Term",
            max_score=100,
            is_published=True,
        )
        score = AssessmentScore.objects.create(assessment=assessment, student=self.student, score=75)

        result = score_result(assessment, score)

        self.assertEqual(result.grade, "B")
        self.assertEqual(result.remark, "Very good")
        self.assertEqual(resolve_grading_profile(self.offering), profile)

    def test_current_default_grade_bands_remain_fallback_without_profile(self):
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="Test",
            max_score=100,
            is_published=True,
        )
        score = AssessmentScore.objects.create(assessment=assessment, student=self.student, score=85)

        result = score_result(assessment, score)

        self.assertEqual(result.grade, "A")
        self.assertEqual(result.remark, "Excellent")

    def test_report_card_applies_promotion_without_rewriting_score(self):
        profile = self._profile(
            level=self.level,
            pass_percentage=50,
            promotion_percentage=70,
            minimum_passed_courses=1,
        )
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="Final",
            max_score=100,
            is_published=True,
        )
        score = AssessmentScore.objects.create(assessment=assessment, student=self.student, score=75)

        report = build_report_card(self.student)
        score.refresh_from_db()

        self.assertEqual(report.grading_profile, profile)
        self.assertEqual(report.report_rule, profile.report_rule)
        self.assertEqual(report.overall_percentage, Decimal("75.00"))
        self.assertEqual(report.overall_grade, "B")
        self.assertEqual(report.promotion_status, "PROMOTED")
        self.assertEqual(score.score, Decimal("75"))

    def test_require_complete_policy_keeps_report_incomplete(self):
        self._profile(
            level=self.level,
            incomplete_result_policy=GradingProfile.REQUIRE_COMPLETE,
        )
        Assessment.objects.create(
            offering=self.offering,
            name="Missing result",
            max_score=100,
            is_published=True,
        )

        report = build_report_card(self.student)

        self.assertIsNone(report.overall_percentage)
        self.assertFalse(report.is_complete)
        self.assertEqual(report.promotion_status, "INCOMPLETE")

    def test_readiness_reports_valid_profile_and_rule(self):
        self._profile(level=self.level)
        readiness = grading_framework_readiness()
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["invalid_profile_count"], 0)
        self.assertEqual(readiness["missing_report_rule_count"], 0)
