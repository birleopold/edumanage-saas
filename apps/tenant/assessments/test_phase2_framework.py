from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Level,
    Program,
)
from apps.tenant.exams.models import Exam, ExamPaper, ExamScore
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile

from .models import (
    Assessment,
    AssessmentScore,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
)
from .services import (
    build_course_result_for_student,
    calculate_scheme_result,
    classify_existing_records,
    ensure_assessment_type_templates,
    ensure_exam_paper_assessment_link,
    infer_assessment_type_code,
    resolve_weighting_scheme,
    scheme_validation_errors,
)


class AssessmentFrameworkTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Phase 2 Test School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.year = AcademicYear.objects.create(name="2026")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.level = Level.objects.create(name="Senior 2", order=2)
        self.program = Program.objects.create(name="General")
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="S2",
            level=self.level,
            program=self.program,
        )
        self.course = Course.objects.create(
            name="Mathematics",
            code="MATH",
            level=self.level,
            program=self.program,
        )
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=self.class_group,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="S-001",
            first_name="Amina",
            last_name="Nabirye",
        )
        self.types = ensure_assessment_type_templates()

    def create_scheme(self, policy=AssessmentWeightingScheme.REQUIRE_COMPLETE):
        scheme = AssessmentWeightingScheme.objects.create(
            code=f"S2-{policy}",
            name=f"S2 {policy}",
            campus=self.campus,
            academic_term=self.term,
            program=self.program,
            total_weight=100,
            missing_score_policy=policy,
            normalize_to_total=True,
            priority=10,
            is_active=True,
        )
        test_component = AssessmentWeightingComponent.objects.create(
            scheme=scheme,
            assessment_type=self.types["TEST"],
            weight=30,
            minimum_occurrences=1,
            order=1,
        )
        exam_component = AssessmentWeightingComponent.objects.create(
            scheme=scheme,
            assessment_type=self.types["EXAM"],
            weight=70,
            minimum_occurrences=1,
            order=2,
        )
        return scheme, test_component, exam_component

    def create_classroom_score(self, component, score=80):
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="Topic Test",
            assessment_type=self.types["TEST"],
            weighting_component=component,
            max_score=100,
            is_published=True,
        )
        result = AssessmentScore.objects.create(
            assessment=assessment,
            student=self.student,
            score=score,
        )
        return assessment, result

    def create_exam_score(self, component, score=60):
        exam = Exam.objects.create(name="Final Examination", term=self.term)
        paper = ExamPaper.objects.create(
            exam=exam,
            offering=self.offering,
            assessment_type=self.types["EXAM"],
            weighting_component=component,
            max_score=100,
            is_published=True,
            results_published=True,
        )
        result = ExamScore.objects.create(paper=paper, student=self.student, score=score)
        return paper, result

    def test_configurable_result_combines_existing_assessment_and_exam_scores(self):
        scheme, test_component, exam_component = self.create_scheme()
        assessment, assessment_score = self.create_classroom_score(test_component, 80)
        paper, exam_score = self.create_exam_score(exam_component, 60)

        result = calculate_scheme_result(scheme, self.offering, self.student)

        self.assertEqual(result.percentage, Decimal("66.00"))
        self.assertTrue(result.is_complete)
        self.assertEqual(AssessmentScore.objects.get(pk=assessment_score.pk).score, Decimal("80"))
        self.assertEqual(ExamScore.objects.get(pk=exam_score.pk).score, Decimal("60"))
        self.assertEqual(assessment.weighting_component, test_component)
        self.assertEqual(paper.weighting_component, exam_component)

    def test_require_complete_does_not_fall_back_to_simple_average(self):
        scheme, test_component, _ = self.create_scheme()
        self.create_classroom_score(test_component, 80)

        result = build_course_result_for_student(self.offering, self.student)

        self.assertEqual(result.scheme, scheme)
        self.assertIsNone(result.weighted_percentage)
        self.assertFalse(result.is_complete)
        self.assertEqual(result.grade, "-")

    def test_zero_missing_and_ignore_missing_policies(self):
        zero_scheme, test_component, _ = self.create_scheme(AssessmentWeightingScheme.ZERO_MISSING)
        self.create_classroom_score(test_component, 80)
        zero_result = calculate_scheme_result(zero_scheme, self.offering, self.student)
        self.assertEqual(zero_result.percentage, Decimal("24.00"))

        zero_scheme.delete()
        ignore_scheme, test_component, _ = self.create_scheme(AssessmentWeightingScheme.IGNORE_MISSING)
        Assessment.objects.update(weighting_component=test_component)
        ignore_result = calculate_scheme_result(ignore_scheme, self.offering, self.student)
        self.assertEqual(ignore_result.percentage, Decimal("80.00"))

    def test_specific_scheme_wins_over_institution_default(self):
        default = AssessmentWeightingScheme.objects.create(
            code="DEFAULT",
            name="Default",
            total_weight=100,
            priority=0,
            is_default=True,
        )
        AssessmentWeightingComponent.objects.create(
            scheme=default,
            assessment_type=self.types["TEST"],
            weight=100,
        )
        specific, _, _ = self.create_scheme()

        self.assertEqual(resolve_weighting_scheme(self.offering), specific)


    def test_equal_scope_and_priority_conflict_is_rejected(self):
        first = AssessmentWeightingScheme.objects.create(
            code="CONFLICT-ONE",
            name="Conflict One",
            campus=self.campus,
            academic_term=self.term,
            program=self.program,
            total_weight=100,
            priority=5,
        )
        second = AssessmentWeightingScheme(
            code="CONFLICT-TWO",
            name="Conflict Two",
            campus=self.campus,
            academic_term=self.term,
            program=self.program,
            total_weight=100,
            priority=5,
        )
        with self.assertRaises(ValidationError):
            second.full_clean()

    def test_invalid_component_total_prevents_resolution(self):
        scheme = AssessmentWeightingScheme.objects.create(
            code="INVALID",
            name="Invalid",
            campus=self.campus,
            total_weight=100,
            priority=99,
        )
        AssessmentWeightingComponent.objects.create(
            scheme=scheme,
            assessment_type=self.types["TEST"],
+            weight=30,
        )

        self.assertTrue(scheme_validation_errors(scheme))
        self.assertIsNone(resolve_weighting_scheme(self.offering))

    def test_component_and_type_mismatch_is_rejected(self):
        scheme, test_component, _ = self.create_scheme()
        assessment = Assessment(
            offering=self.offering,
            name="Wrong Type",
            assessment_type=self.types["EXAM"],
            weighting_component=test_component,
            max_score=100,
        )
        with self.assertRaises(ValidationError):
            assessment.full_clean()

    def test_classification_is_additive_and_preserves_scores_and_legacy_weight(self):
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="Mid-Term Test",
            max_score=50,
            weight=25,
            is_published=True,
        )
        score = AssessmentScore.objects.create(
            assessment=assessment,
            student=self.student,
            score=40,
        )

        summary = classify_existing_records(include_exam_papers=False)
        assessment.refresh_from_db()
        score.refresh_from_db()

        self.assertEqual(summary["assessments_classified"], 1)
        self.assertEqual(assessment.assessment_type.code, "MOT")
        self.assertEqual(assessment.weight, Decimal("25"))
        self.assertEqual(score.score, Decimal("40"))


    def test_exam_paper_compatibility_link_does_not_copy_scores(self):
        scheme, _, exam_component = self.create_scheme()
        paper, exam_score = self.create_exam_score(exam_component, 67)

        linked = ensure_exam_paper_assessment_link(paper, create=True)
        paper.refresh_from_db()
        exam_score.refresh_from_db()

        self.assertEqual(paper.linked_assessment, linked)
        self.assertEqual(linked.offering, self.offering)
        self.assertEqual(linked.assessment_type, self.types["EXAM"])
        self.assertFalse(AssessmentScore.objects.filter(assessment=linked).exists())
        self.assertEqual(exam_score.score, Decimal("67"))

    def test_legacy_assessment_without_scheme_remains_supported(self):
        assessment = Assessment.objects.create(
            offering=self.offering,
            name="Legacy Test",
            max_score=100,
            weight=40,
            is_published=True,
        )
        AssessmentScore.objects.create(assessment=assessment, student=self.student, score=75)

        result = build_course_result_for_student(self.offering, self.student)

        self.assertIsNone(result.scheme)
        self.assertEqual(result.weighted_percentage, Decimal("75.00"))
        self.assertEqual(result.grade, "B")

    def test_uganda_and_neutral_name_inference(self):
        self.assertEqual(infer_assessment_type_code("Activity of Integration"), "AOI")
        self.assertEqual(infer_assessment_type_code("End of Term Examination"), "EOT")
        self.assertEqual(infer_assessment_type_code("Laboratory Practical"), "PRACTICAL")
        self.assertEqual(infer_assessment_type_code("Research Project"), "PROJECT")
