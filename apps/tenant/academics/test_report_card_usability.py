from decimal import Decimal

from django.test import TestCase

from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile

from .models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream
from .reports import ReportCard


class ReportCardUsabilityTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Report Test School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            code="REPORT",
            is_default=True,
        )
        self.year = AcademicYear.objects.create(name="2031")
        self.previous_term = AcademicTerm.objects.create(
            year=self.year,
            name="Term 1",
            order=1,
        )
        self.current_term = AcademicTerm.objects.create(
            year=self.year,
            name="Term 2",
            order=2,
        )
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Form 2",
            code="F2-REPORT",
        )
        self.stream = Stream.objects.create(
            class_group=self.class_group,
            name="East",
            capacity=40,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="REPORT-001",
            first_name="Sarah",
            last_name="Auma",
        )
        self.course = Course.objects.create(name="Mathematics", code="MATH-REPORT")
        self.previous_offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.previous_term,
            class_group=self.class_group,
        )
        self.current_offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.current_term,
            class_group=self.class_group,
        )
        Enrollment.objects.create(
            campus=self.campus,
            offering=self.previous_offering,
            student=self.student,
        )
        Enrollment.objects.create(
            campus=self.campus,
            offering=self.current_offering,
            student=self.student,
        )

        self.previous_assessment = Assessment.objects.create(
            offering=self.previous_offering,
            name="Term result",
            max_score=100,
            weight=100,
            is_published=True,
        )
        AssessmentScore.objects.create(
            assessment=self.previous_assessment,
            student=self.student,
            score=50,
        )
        self.current_assessment = Assessment.objects.create(
            offering=self.current_offering,
            name="Term result",
            max_score=100,
            weight=100,
            is_published=True,
        )
        self.current_score = AssessmentScore.objects.create(
            assessment=self.current_assessment,
            student=self.student,
            score=70,
            report_comment="Sarah is making strong and consistent progress in Mathematics.",
            report_comment_ai_assisted=True,
        )

    def test_published_teacher_feedback_is_included_on_report_card(self):
        data = ReportCard(self.student.pk, self.current_term.pk).to_dict()

        self.assertEqual(len(data["teacher_comments"]), 1)
        self.assertEqual(
            data["teacher_comments"][0]["teacher_comment"],
            "Sarah is making strong and consistent progress in Mathematics.",
        )
        self.assertTrue(data["teacher_comments"][0]["teacher_comment_ai_assisted"])

    def test_unpublished_teacher_feedback_never_leaks_to_report_card(self):
        draft = Assessment.objects.create(
            offering=self.current_offering,
            name="Draft assessment",
            max_score=100,
            weight=100,
            is_published=False,
        )
        AssessmentScore.objects.create(
            assessment=draft,
            student=self.student,
            score=99,
            report_comment="PRIVATE DRAFT COMMENT",
        )

        data = ReportCard(self.student.pk, self.current_term.pk).to_dict()
        comments = " ".join(item["teacher_comment"] for item in data["teacher_comments"])

        self.assertNotIn("PRIVATE DRAFT COMMENT", comments)
        self.assertIn("strong and consistent progress", comments)

    def test_progress_compares_with_immediately_previous_term(self):
        progress = ReportCard(self.student.pk, self.current_term.pk).get_progress()

        self.assertTrue(progress["available"])
        self.assertEqual(progress["trend"], "improving")
        self.assertEqual(progress["previous_average"], Decimal("50.00"))
        self.assertEqual(progress["current_average"], Decimal("70.00"))
        self.assertEqual(progress["change"], Decimal("20.00"))

    def test_zero_percentage_is_a_real_result_not_missing_data(self):
        self.current_score.score = Decimal("0")
        self.current_score.save(update_fields=["score"])

        summary = ReportCard(self.student.pk, self.current_term.pk).get_summary()

        self.assertEqual(summary["average"], Decimal("0.00"))
        self.assertEqual(summary["highest"], Decimal("0.00"))
        self.assertEqual(summary["lowest"], Decimal("0.00"))
        self.assertEqual(summary["scored_subjects"], 1)
