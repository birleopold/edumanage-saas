from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    Stream,
)
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .activity_forms import LearningActivityPolicyForm
from .models import Assignment, AssignmentSubmission, LearningActivity
from .workflow_models import (
    AssignmentGroup,
    AssignmentGroupMember,
    GroupSubmission,
    LearningActivityProfile,
    SubmissionWorkflow,
)
from .workflow_services import (
    classify_submission_time,
    coursework_workflow_readiness,
    transition_submission,
)


class DetailedCourseworkWorkflowTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        year = AcademicYear.objects.create(name="2026-WORKFLOW")
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1)
        course = Course.objects.create(name="Biology", code="BIO-WF")
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="Senior Two Workflow",
        )
        self.stream = Stream.objects.create(
            class_group=self.class_group,
            name="North",
        )
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=self.class_group,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="WF-001",
            first_name="Workflow",
            last_name="Learner",
        )
        self.other_student = StudentProfile.objects.create(
            campus=self.campus,
            stream=self.stream,
            student_id="WF-002",
            first_name="Second",
            last_name="Learner",
        )
        Enrollment.objects.create(
            campus=self.campus,
            offering=self.offering,
            student=self.student,
        )
        Enrollment.objects.create(
            campus=self.campus,
            offering=self.offering,
            student=self.other_student,
        )
        self.assignment = Assignment.objects.create(
            title="Field investigation",
            instructions="Collect and analyse samples.",
            max_score=Decimal("50"),
            campus=self.campus,
            class_group=self.class_group,
            stream=self.stream,
            offering=self.offering,
            due_date=timezone.now() + timedelta(hours=1),
        )
        self.activity = LearningActivity.objects.get(assignment=self.assignment)

    def test_activity_receives_explicit_workflow_profile(self):
        self.assertTrue(hasattr(self.activity, "workflow_profile"))
        self.assertEqual(
            self.activity.workflow_profile.detailed_kind,
            LearningActivityProfile.ASSIGNMENT,
        )

    def test_policy_form_persists_exact_activity_type(self):
        form = LearningActivityPolicyForm(
            data={
                "kind": self.activity.kind,
                "detailed_kind": LearningActivityProfile.GROUP_ASSIGNMENT,
                "position": 1,
                "estimated_minutes": 90,
                "completion_policy": LearningActivity.COMPLETION_SUBMISSION,
                "submission_policy": LearningActivity.SUBMISSION_REQUIRED,
                "group_work": "on",
                "resubmission_allowed": "on",
                "maximum_attempts": 2,
                "late_grace_minutes": 30,
                "competency_tracking": "on",
                "competency_framework_key": "NCDC-AOI",
                "assessment_type": "",
                "weighting_component": "",
                "local_aliases": "{}",
                "settings": "{}",
                "is_active": "on",
            },
            instance=self.activity,
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        form.save()
        self.activity.workflow_profile.refresh_from_db()
        profile = self.activity.workflow_profile
        self.assertEqual(profile.detailed_kind, LearningActivityProfile.GROUP_ASSIGNMENT)
        self.assertTrue(profile.group_work)
        self.assertEqual(profile.maximum_attempts, 2)
        self.assertEqual(profile.late_grace_minutes, 30)

    def test_group_capacity_is_enforced(self):
        profile = self.activity.workflow_profile
        profile.detailed_kind = LearningActivityProfile.GROUP_ASSIGNMENT
        profile.group_work = True
        profile.save(update_fields=["detailed_kind", "group_work", "updated_at"])
        group = AssignmentGroup.objects.create(
            activity=self.activity,
            name="Team A",
            capacity=1,
        )
        AssignmentGroupMember.objects.create(group=group, student=self.student)
        second = AssignmentGroupMember(group=group, student=self.other_student)

        with self.assertRaises(ValidationError) as error:
            second.full_clean()

        self.assertIn("student", error.exception.message_dict)

    def test_date_and_datetime_deadlines_classify_lateness(self):
        before_deadline = self.assignment.due_date - timedelta(minutes=5)
        after_deadline = self.assignment.due_date + timedelta(minutes=5)

        early, early_status = classify_submission_time(
            self.activity,
            before_deadline,
        )
        late, late_status = classify_submission_time(
            self.activity,
            after_deadline,
        )

        self.assertFalse(early)
        self.assertEqual(early_status, SubmissionWorkflow.SUBMITTED)
        self.assertTrue(late)
        self.assertEqual(late_status, SubmissionWorkflow.LATE)

    def test_resubmission_transition_respects_attempt_limit(self):
        profile = self.activity.workflow_profile
        profile.resubmission_allowed = True
        profile.maximum_attempts = 2
        profile.save(
            update_fields=[
                "resubmission_allowed",
                "maximum_attempts",
                "updated_at",
            ]
        )
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            activity=self.activity,
            student=self.student,
            submitted_at=timezone.now(),
        )
        workflow = submission.workflow
        workflow.status = SubmissionWorkflow.RESUBMISSION_REQUIRED
        workflow.save(update_fields=["status", "updated_at"])

        transition_submission(workflow, SubmissionWorkflow.RESUBMITTED)

        workflow.refresh_from_db()
        self.assertEqual(workflow.status, SubmissionWorkflow.RESUBMITTED)
        self.assertEqual(workflow.attempt_count, 2)

    def test_group_submission_requires_active_member(self):
        profile = self.activity.workflow_profile
        profile.detailed_kind = LearningActivityProfile.GROUP_ASSIGNMENT
        profile.group_work = True
        profile.save(update_fields=["detailed_kind", "group_work", "updated_at"])
        group = AssignmentGroup.objects.create(activity=self.activity, name="Team B")
        submission = GroupSubmission(
            activity=self.activity,
            group=group,
            submitted_by=self.student,
        )

        with self.assertRaises(ValidationError) as error:
            submission.full_clean()

        self.assertIn("submitted_by", error.exception.message_dict)

    def test_readiness_reports_complete_profiles_and_workflows(self):
        AssignmentSubmission.objects.create(
            assignment=self.assignment,
            activity=self.activity,
            student=self.student,
        )

        readiness = coursework_workflow_readiness()

        self.assertEqual(readiness["missing_profile_count"], 0)
        self.assertEqual(readiness["missing_workflow_count"], 0)
