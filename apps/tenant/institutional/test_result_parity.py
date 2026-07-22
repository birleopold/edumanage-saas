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
    Stream,
)
from apps.tenant.assessments.models import (
    Assessment,
    AssessmentScore,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
    GradingProfile,
    ReportRule,
)
from apps.tenant.assessments.result_facade import (
    build_result_snapshot,
    course_result_rows,
)
from apps.tenant.exams.models import Exam, ExamPaper, ExamScore
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .services import academic_summary, course_results


class ResultParityTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        year = AcademicYear.objects.create(name="2026-PARITY")
        self.term = AcademicTerm.objects.create(
            year=year,
            name="Term 1",
            order=1,
            is_current=True,
        )
        self.course = Course.objects.create(
            name="Integrated Mathematics",
            code="PARITY-MATH",
            credits=3,
        )
        class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Parity Class",
        )
        stream = Stream.objects.create(class_group=class_group, name="East")
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=class_group,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=stream,
            student_id="PARITY-001",
            first_name="Parity",
            last_name="Learner",
        )
        Enrollment.objects.create(
            campus=self.campus,
            offering=self.offering,
            student=self.student,
        )

        coursework_type = AssessmentType.objects.create(
            code="PARITY-CW",
            name="Coursework",
            kind=AssessmentType.COURSEWORK,
        )
        exam_type = AssessmentType.objects.create(
            code="PARITY-EXAM",
            name="Examination",
            kind=AssessmentType.EXAMINATION,
        )
        scheme = AssessmentWeightingScheme.objects.create(
            code="PARITY-SCHEME",
            name="30/70 Scheme",
            campus=self.campus,
            academic_term=self.term,
            total_weight=Decimal("100"),
            is_default=True,
            is_active=True,
        )
        coursework_component = AssessmentWeightingComponent.objects.create(
            scheme=scheme,
            assessment_type=coursework_type,
            weight=Decimal("30"),
            order=1,
        )
        exam_component = AssessmentWeightingComponent.objects.create(
            scheme=scheme,
            assessment_type=exam_type,
            weight=Decimal("70"),
            order=2,
        )
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="Coursework",
            assessment_type=coursework_type,
            weighting_component=coursework_component,
            max_score=Decimal("100"),
            is_published=True,
        )
        AssessmentScore.objects.create(
            assessment=assessment,
            student=self.student,
            score=Decimal("80"),
        )
        exam = Exam.objects.create(name="Final Examination", term=self.term)
        paper = ExamPaper.objects.create(
            exam=exam,
            offering=self.offering,
            assessment_type=exam_type,
            weighting_component=exam_component,
            max_score=Decimal("100"),
            is_published=True,
            results_published=True,
            report_cards_enabled=True,
        )
        ExamScore.objects.create(
            paper=paper,
            student=self.student,
            score=Decimal("60"),
        )

        scale = GradingScale.objects.create(
            name="Parity Scale",
            is_default=True,
            is_active=True,
        )
        GradeRange.objects.create(
            scale=scale,
            min_score=Decimal("0"),
            max_score=Decimal("100"),
            grade="P",
            remark="Pass",
            grade_point=Decimal("3.00"),
            order=1,
        )
        profile = GradingProfile.objects.create(
            code="PARITY-GRADING",
            name="Parity Grading",
            grading_scale=scale,
            campus=self.campus,
            academic_term=self.term,
            is_default=True,
            is_active=True,
        )
        ReportRule.objects.create(grading_profile=profile)

    def test_portal_and_institutional_course_results_match(self):
        snapshot = build_result_snapshot(
            self.student,
            academic_term=self.term,
        )
        portal_rows = course_result_rows(snapshot)
        institutional_rows = course_results(self.student, self.term)

        self.assertEqual(len(portal_rows), 1)
        self.assertEqual(len(institutional_rows), 1)
        self.assertEqual(portal_rows[0]["percentage"], Decimal("66.00"))
        self.assertEqual(
            institutional_rows[0]["percentage"],
            portal_rows[0]["percentage"],
        )
        self.assertEqual(institutional_rows[0]["grade"], portal_rows[0]["grade"])
        self.assertNotEqual(institutional_rows[0]["percentage"], Decimal("70.00"))

    def test_institutional_summary_uses_authoritative_overall(self):
        snapshot = build_result_snapshot(
            self.student,
            academic_term=self.term,
        )
        summary = academic_summary(self.student, self.term)

        self.assertEqual(summary["mean"], snapshot.overall_percentage)
        self.assertEqual(summary["mean"], Decimal("66.00"))
        self.assertEqual(summary["overall_grade"], snapshot.overall_grade)
