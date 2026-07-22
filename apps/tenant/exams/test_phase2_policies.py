from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    Course,
    CourseOffering,
)
from apps.tenant.assessments.models import AssessmentType
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import Exam, ExamPaper, ExamScore
from .policy_models import ExamPaperPolicy, ExamScorePolicy
from .policy_services import effective_score, exam_policy_readiness


class ExamPolicyTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Exam Policy School")
        self.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        self.teacher = TeacherProfile.objects.create(
            campus=self.campus,
            first_name="Exam",
            last_name="Teacher",
        )
        year = AcademicYear.objects.create(name="2026")
        self.term = AcademicTerm.objects.create(year=year, name="Term 1", order=1)
        course = Course.objects.create(name="English", code="ENG")
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=self.term,
            teacher=self.teacher,
        )
        self.exam = Exam.objects.create(name="End of Term", term=self.term)
        self.assessment_type = AssessmentType.objects.create(
            code="EXAM-POLICY",
            name="Formal Examination",
            kind=AssessmentType.EXAMINATION,
        )
        self.competency_type = AssessmentType.objects.create(
            code="EXAM-COMPETENCY",
            name="Competency Examination",
            kind=AssessmentType.COMPETENCY,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="EX-001",
            first_name="Exam",
            last_name="Learner",
        )

    def make_paper(self, **overrides):
        values = {
            "exam": self.exam,
            "offering": self.offering,
            "assessment_type": self.assessment_type,
            "max_score": Decimal("100"),
            "report_cards_enabled": True,
        }
        values.update(overrides)
        return ExamPaper.objects.create(**values)

    def test_new_paper_receives_explicit_policy(self):
        paper = self.make_paper()

        self.assertTrue(hasattr(paper, "policy"))
        self.assertEqual(paper.policy.grading_mode, ExamPaperPolicy.NUMERIC)
        self.assertEqual(paper.policy.responsible_teacher, self.teacher)
        self.assertTrue(paper.policy.show_on_report)

    def test_competency_paper_defaults_to_competency_mode(self):
        paper = self.make_paper(assessment_type=self.competency_type)

        self.assertEqual(paper.policy.grading_mode, ExamPaperPolicy.COMPETENCY)

    def test_deferred_policy_requires_makeup_permission(self):
        paper = self.make_paper()
        paper.policy.absence_policy = ExamPaperPolicy.DEFERRED
        paper.policy.allow_makeup = False

        with self.assertRaises(ValidationError) as error:
            paper.policy.full_clean()

        self.assertIn("allow_makeup", error.exception.message_dict)

    def test_zero_absence_policy_produces_effective_zero(self):
        paper = self.make_paper()
        paper.policy.absence_policy = ExamPaperPolicy.ZERO
        paper.policy.save(update_fields=["absence_policy", "updated_at"])
        score = ExamScore.objects.create(
            paper=paper,
            student=self.student,
            score=None,
        )
        score.policy.attendance_status = ExamScorePolicy.ABSENT
        score.policy.full_clean()
        score.policy.save(update_fields=["attendance_status", "updated_at"])

        self.assertEqual(effective_score(paper, score), Decimal("0"))

    def test_makeup_score_replaces_original_attempt(self):
        original = self.make_paper()
        original.policy.allow_makeup = True
        original.policy.save(update_fields=["allow_makeup", "updated_at"])
        makeup_exam = Exam.objects.create(name="Makeup Examination", term=self.term)
        makeup = ExamPaper.objects.create(
            exam=makeup_exam,
            offering=self.offering,
            assessment_type=self.assessment_type,
            max_score=Decimal("100"),
            report_cards_enabled=True,
        )
        makeup.policy.makeup_for = original
        makeup.policy.full_clean()
        makeup.policy.save(update_fields=["makeup_for", "updated_at"])
        original_score = ExamScore.objects.create(
            paper=original,
            student=self.student,
            score=None,
        )
        replacement_score = ExamScore.objects.create(
            paper=makeup,
            student=self.student,
            score=Decimal("74"),
        )
        original_score.policy.attendance_status = ExamScorePolicy.MAKEUP_PENDING
        original_score.policy.makeup_completed_by = replacement_score
        original_score.policy.full_clean()
        original_score.policy.save()

        self.assertEqual(effective_score(original, original_score), Decimal("74"))

    def test_readiness_detects_complete_policy_records(self):
        paper = self.make_paper()
        ExamScore.objects.create(
            paper=paper,
            student=self.student,
            score=Decimal("65"),
        )

        readiness = exam_policy_readiness()

        self.assertEqual(readiness["missing_paper_policy_count"], 0)
        self.assertEqual(readiness["missing_score_policy_count"], 0)
        self.assertEqual(readiness["invalid_paper_policy_count"], 0)
