from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User

from .activity_services import (
    learning_activity_readiness,
    sync_all_learning_activities,
    sync_learning_activity,
    unified_learner_progress_summary,
    visible_learning_activities_for_student,
)
from .models import (
    Assignment,
    AssignmentSubmission,
    CourseworkComment,
    CourseworkProgress,
    LearningActivity,
    LearningMaterial,
)


class UnifiedLearningActivityTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(organization=org, name="Phase 3 Other Campus")
        self.year = AcademicYear.objects.create(name="2026-P3")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.course = Course.objects.create(name="Integrated Science", code="P3SCI")
        self.class_group = ClassGroup.objects.create(campus=self.campus, name="Senior Three")
        self.other_class_group = ClassGroup.objects.create(campus=self.other_campus, name="Senior Four")
        self.stream = Stream.objects.create(class_group=self.class_group, name="East")
        self.other_stream = Stream.objects.create(class_group=self.other_class_group, name="West")

        self.admin_user = self._user_with_role("phase3_admin", Role.ADMIN)
        self.teacher_user = self._user_with_role("phase3_teacher", Role.TEACHER)
        self.student_user = self._user_with_role("phase3_student", Role.STUDENT)
        self.other_student_user = self._user_with_role("phase3_other_student", Role.STUDENT)
        self.teacher = TeacherProfile.objects.create(
            user=self.teacher_user,
            campus=self.campus,
            first_name="Unified",
            last_name="Teacher",
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            campus=self.campus,
            stream=self.stream,
            first_name="Unified",
            last_name="Learner",
            student_id="P3-001",
        )
        self.other_student = StudentProfile.objects.create(
            user=self.other_student_user,
            campus=self.other_campus,
            stream=self.other_stream,
            first_name="Other",
            last_name="Learner",
            student_id="P3-002",
        )
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=self.course,
            term=self.term,
            class_group=self.class_group,
            teacher=self.teacher,
        )
        self.other_offering = CourseOffering.objects.create(
            campus=self.other_campus,
            course=self.course,
            term=self.term,
            class_group=self.other_class_group,
        )
        Enrollment.objects.create(campus=self.campus, offering=self.offering, student=self.student)
        Enrollment.objects.create(campus=self.other_campus, offering=self.other_offering, student=self.other_student)

    def _user_with_role(self, username: str, role_code: str) -> User:
        role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code.title()})
        user = User.objects.create_user(username=username, password="test-pass-123")
        user.roles.add(role)
        return user

    def test_new_sources_are_synchronized_without_replacing_source_records(self):
        material = LearningMaterial.objects.create(
            type=LearningMaterial.VIDEO_LESSON,
            title="Cell division video",
            campus=self.campus,
            class_group=self.class_group,
            offering=self.offering,
            created_by=self.teacher_user,
        )
        assignment = Assignment.objects.create(
            title="Laboratory practical report",
            campus=self.campus,
            class_group=self.class_group,
            offering=self.offering,
            max_score=Decimal("40"),
            created_by=self.teacher_user,
        )

        material_activity = LearningActivity.objects.get(material=material)
        assignment_activity = LearningActivity.objects.get(assignment=assignment)
        self.assertEqual(material_activity.kind, LearningActivity.VIDEO)
        self.assertEqual(material_activity.completion_policy, LearningActivity.COMPLETION_VIEW)
        self.assertEqual(assignment_activity.kind, LearningActivity.PRACTICAL)
        self.assertEqual(assignment_activity.submission_policy, LearningActivity.SUBMISSION_REQUIRED)
        self.assertTrue(LearningMaterial.objects.filter(pk=material.pk, title="Cell division video").exists())
        self.assertTrue(Assignment.objects.filter(pk=assignment.pk, max_score=Decimal("40")).exists())

    def test_sync_is_idempotent_and_preserves_administrator_policy(self):
        assignment = Assignment.objects.create(
            title="Research project",
            campus=self.campus,
            offering=self.offering,
            created_by=self.teacher_user,
        )
        activity = LearningActivity.objects.get(assignment=assignment)
        activity.position = 17
        activity.completion_policy = LearningActivity.COMPLETION_SCORE
        activity.save(update_fields=["position", "completion_policy", "updated_at"])

        first = sync_learning_activity(assignment)
        second = sync_learning_activity(assignment)
        activity.refresh_from_db()

        self.assertFalse(first.created)
        self.assertFalse(second.created)
        self.assertEqual(LearningActivity.objects.filter(assignment=assignment).count(), 1)
        self.assertEqual(activity.position, 17)
        self.assertEqual(activity.completion_policy, LearningActivity.COMPLETION_SCORE)

    def test_submission_comment_and_progress_receive_metadata_only_links(self):
        assignment = Assignment.objects.create(
            title="Essay assignment",
            campus=self.campus,
            offering=self.offering,
            created_by=self.teacher_user,
        )
        activity = LearningActivity.objects.get(assignment=assignment)
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            text_answer="Original answer",
            score=Decimal("18"),
        )
        comment = CourseworkComment.objects.create(
            assignment=assignment,
            user=self.student_user,
            body="Please clarify question two.",
        )
        progress = CourseworkProgress.objects.create(
            assignment=assignment,
            student=self.student,
            percent_complete=Decimal("65"),
        )
        submission.refresh_from_db()
        comment.refresh_from_db()
        progress.refresh_from_db()

        self.assertEqual(submission.activity_id, activity.pk)
        self.assertEqual(comment.activity_id, activity.pk)
        self.assertEqual(progress.activity_id, activity.pk)
        self.assertEqual(submission.text_answer, "Original answer")
        self.assertEqual(submission.score, Decimal("18"))
        self.assertEqual(progress.percent_complete, Decimal("65"))

    def test_unified_visibility_uses_existing_student_scope_rules(self):
        visible = LearningMaterial.objects.create(
            type=LearningMaterial.NOTES,
            title="Visible notes",
            campus=self.campus,
            class_group=self.class_group,
            offering=self.offering,
            publish_at=timezone.now(),
        )
        hidden = Assignment.objects.create(
            title="Other campus assignment",
            campus=self.other_campus,
            class_group=self.other_class_group,
            offering=self.other_offering,
            publish_at=timezone.now(),
        )

        activities = visible_learning_activities_for_student(self.student)
        source_ids = {(item.source_type, item.source.pk) for item in activities}
        self.assertIn(("material", visible.pk), source_ids)
        self.assertNotIn(("assignment", hidden.pk), source_ids)

    def test_unified_progress_uses_existing_submission_and_progress_values(self):
        assignment = Assignment.objects.create(
            title="Submitted task",
            campus=self.campus,
            offering=self.offering,
            publish_at=timezone.now(),
            created_by=self.teacher_user,
        )
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            submitted_at=timezone.now(),
            text_answer="Submitted unchanged",
        )

        summary = unified_learner_progress_summary(self.student)

        self.assertEqual(summary["total_items"], 1)
        self.assertEqual(summary["completed_items"], 1)
        submission.refresh_from_db()
        self.assertEqual(submission.text_answer, "Submitted unchanged")

    def test_readiness_and_dry_run_are_read_only(self):
        material = LearningMaterial.objects.create(
            type=LearningMaterial.NOTES,
            title="Readiness notes",
            campus=self.campus,
            offering=self.offering,
        )
        activity = LearningActivity.objects.get(material=material)
        activity.delete()
        count_before = LearningActivity.objects.count()

        preview = sync_all_learning_activities(dry_run=True)

        self.assertEqual(preview["materials_to_create"], 1)
        self.assertEqual(LearningActivity.objects.count(), count_before)
        self.assertFalse(learning_activity_readiness()["ready"])

    def test_full_admin_can_open_activity_framework(self):
        LearningMaterial.objects.create(type=LearningMaterial.NOTES, title="Admin notes")
        self.client.login(username="phase3_admin", password="test-pass-123")
        response = self.client.get(reverse("admin_coursework_activity_framework"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unified Learning Activities")

    def test_student_cannot_open_activity_framework(self):
        self.client.login(username="phase3_student", password="test-pass-123")
        response = self.client.get(reverse("admin_coursework_activity_framework"))
        self.assertNotEqual(response.status_code, 200)
