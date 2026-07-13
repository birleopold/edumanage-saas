from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment
from apps.tenant.analytics.intelligence_models import ReportCardCommentSuggestion
from apps.tenant.assessments.comment_suggestions import build_report_comment_suggestion
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.assessments.services import score_result
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.discipline.models import Incident
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User


class ReportCommentSuggestionTests(TestCase):
    def setUp(self):
        self.teacher_role, _ = Role.objects.get_or_create(code=Role.TEACHER, defaults={"name": "Teacher"})
        self.teacher_user = User.objects.create_user(username="comment_teacher", password="test-pass-123")
        self.teacher_user.roles.add(self.teacher_role)

        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.teacher = TeacherProfile.objects.create(
            user=self.teacher_user,
            first_name="Tina",
            last_name="Teacher",
            campus=self.campus,
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
        self.class_group = ClassGroup.objects.create(name="Senior One", campus=self.campus, is_active=True)
        self.course = Course.objects.create(name="Mathematics", is_active=True)
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=self.class_group,
            teacher=self.teacher,
        )
        self.student = StudentProfile.objects.create(
            first_name="Ada",
            last_name="Learner",
            campus=self.campus,
            student_id="AI-001",
            is_active=True,
        )
        Enrollment.objects.create(offering=self.offering, student=self.student, campus=self.campus)
        self.previous_assessment = Assessment.objects.create(
            offering=self.offering,
            name="Quiz 1",
            max_score=Decimal("100"),
            date=date(2026, 3, 1),
            is_published=True,
        )
        AssessmentScore.objects.create(
            assessment=self.previous_assessment,
            student=self.student,
            score=Decimal("60"),
            graded_by=self.teacher,
        )
        self.assessment = Assessment.objects.create(
            offering=self.offering,
            name="Quiz 2",
            max_score=Decimal("100"),
            date=date(2026, 3, 15),
            is_published=True,
        )
        self.score = AssessmentScore.objects.create(
            assessment=self.assessment,
            student=self.student,
            score=Decimal("82"),
            graded_by=self.teacher,
        )

    def test_suggestion_uses_performance_trend_attendance_and_conduct(self):
        session = AttendanceSession.objects.create(offering=self.offering, date=date(2026, 3, 10), taken_by=self.teacher)
        AttendanceEntry.objects.create(session=session, student=self.student, status=AttendanceEntry.PRESENT)
        Incident.objects.create(
            student=self.student,
            reported_by=self.teacher,
            title="Late homework",
            incident_date=date(2026, 3, 11),
            status=Incident.OPEN,
        )

        suggestion = build_report_comment_suggestion(self.assessment, self.score, self.student)

        self.assertEqual(suggestion.performance_band, "excellent")
        self.assertEqual(suggestion.trend, "improving")
        self.assertEqual(suggestion.attendance_percentage, Decimal("100.00"))
        self.assertEqual(suggestion.discipline_incidents, 1)
        self.assertIn("excellent achievement", suggestion.comment)
        self.assertIn("conduct record", suggestion.comment)

    def test_teacher_comment_suggestions_endpoint_persists_term_comment(self):
        self.client.login(username="comment_teacher", password="test-pass-123")
        resp = self.client.get(reverse("teacher_assessments_comment_suggestions", kwargs={"pk": self.assessment.pk}))

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["assessment"], self.assessment.id)
        self.assertEqual(len(data["suggestions"]), 1)
        self.assertIn("comment", data["suggestions"][0])
        self.assertTrue(ReportCardCommentSuggestion.objects.filter(student=self.student, term=self.term).exists())

    def test_teacher_grade_page_renders_suggested_comments(self):
        self.client.login(username="comment_teacher", password="test-pass-123")
        resp = self.client.get(reverse("teacher_assessments_grade", kwargs={"pk": self.assessment.pk}))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "AI comment")
        self.assertContains(resp, "Use comment")

    def test_teacher_can_save_ai_assisted_report_comment(self):
        self.client.login(username="comment_teacher", password="test-pass-123")
        comment = "Ada has demonstrated excellent achievement in Mathematics."
        resp = self.client.post(
            reverse("teacher_assessments_grade", kwargs={"pk": self.assessment.pk}),
            {
                "student_ids": [str(self.student.id)],
                f"score_{self.student.id}": "82",
                f"note_{self.student.id}": "Keep practicing algebra.",
                f"report_comment_{self.student.id}": comment,
                f"report_comment_ai_{self.student.id}": "1",
            },
        )

        self.assertEqual(resp.status_code, 302)
        self.score.refresh_from_db()
        self.assertEqual(self.score.report_comment, comment)
        self.assertTrue(self.score.report_comment_ai_assisted)

        result = score_result(self.assessment, self.score)
        self.assertEqual(result.report_comment, comment)
        self.assertTrue(result.report_comment_ai_assisted)
