from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AssignmentSubmission, LearningActivity
from .workflow_models import (
    AssignmentGroup,
    AssignmentGroupMember,
    GroupSubmission,
    LearningActivityProfile,
    SubmissionWorkflow,
)


TRANSITIONS = {
    SubmissionWorkflow.DRAFT: {
        SubmissionWorkflow.SUBMITTED,
        SubmissionWorkflow.LATE,
    },
    SubmissionWorkflow.SUBMITTED: {
        SubmissionWorkflow.RETURNED,
        SubmissionWorkflow.RESUBMISSION_REQUIRED,
        SubmissionWorkflow.MARKED,
    },
    SubmissionWorkflow.LATE: {
        SubmissionWorkflow.EXCUSED_LATE,
        SubmissionWorkflow.RETURNED,
        SubmissionWorkflow.RESUBMISSION_REQUIRED,
        SubmissionWorkflow.MARKED,
    },
    SubmissionWorkflow.EXCUSED_LATE: {
        SubmissionWorkflow.RETURNED,
        SubmissionWorkflow.RESUBMISSION_REQUIRED,
        SubmissionWorkflow.MARKED,
    },
    SubmissionWorkflow.RETURNED: {
        SubmissionWorkflow.RESUBMITTED,
    },
    SubmissionWorkflow.RESUBMISSION_REQUIRED: {
        SubmissionWorkflow.RESUBMITTED,
    },
    SubmissionWorkflow.RESUBMITTED: {
        SubmissionWorkflow.RETURNED,
        SubmissionWorkflow.RESUBMISSION_REQUIRED,
        SubmissionWorkflow.MARKED,
    },
    SubmissionWorkflow.MARKED: set(),
}


def activity_profile_for(activity: LearningActivity) -> LearningActivityProfile:
    try:
        return activity.workflow_profile
    except LearningActivityProfile.DoesNotExist:
        return LearningActivityProfile.objects.create(
            activity=activity,
            detailed_kind=(
                activity.kind
                if activity.kind in dict(LearningActivityProfile.DETAILED_KIND_CHOICES)
                else LearningActivityProfile.OTHER
            ),
        )


def submission_workflow_for(submission: AssignmentSubmission) -> SubmissionWorkflow:
    try:
        return submission.workflow
    except SubmissionWorkflow.DoesNotExist:
        return SubmissionWorkflow.objects.create(submission=submission)


def _aware_datetime(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.max)
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def submission_deadline(activity: LearningActivity):
    due_at = _aware_datetime(activity.due_at)
    profile = activity_profile_for(activity)
    if due_at and profile.late_grace_minutes:
        due_at += timedelta(minutes=profile.late_grace_minutes)
    return due_at


def classify_submission_time(
    activity: LearningActivity,
    submitted_at=None,
) -> tuple[bool, str]:
    submitted_at = _aware_datetime(submitted_at or timezone.now())
    due_at = submission_deadline(activity)
    is_late = bool(due_at and submitted_at > due_at)
    return is_late, (
        SubmissionWorkflow.LATE if is_late else SubmissionWorkflow.SUBMITTED
    )


@transaction.atomic
def transition_submission(
    workflow: SubmissionWorkflow,
    target_status: str,
    *,
    actor=None,
    reason: str = "",
) -> SubmissionWorkflow:
    allowed = TRANSITIONS.get(workflow.status, set())
    if target_status not in allowed:
        raise ValidationError(
            f"Cannot move submission from {workflow.get_status_display()} to "
            f"{dict(SubmissionWorkflow.STATUS_CHOICES).get(target_status, target_status)}."
        )

    profile = workflow.activity_profile
    now = timezone.now()
    if target_status == SubmissionWorkflow.EXCUSED_LATE:
        workflow.is_late = True
        workflow.late_excused = True
        workflow.late_reason = reason.strip()
    elif target_status in {
        SubmissionWorkflow.RETURNED,
        SubmissionWorkflow.RESUBMISSION_REQUIRED,
    }:
        workflow.returned_at = now
        if reason:
            workflow.settings = {
                **dict(workflow.settings or {}),
                "return_reason": reason.strip(),
                "returned_by": getattr(actor, "pk", None),
            }
    elif target_status == SubmissionWorkflow.RESUBMITTED:
        if profile and not profile.resubmission_allowed:
            raise ValidationError("This activity does not allow resubmission.")
        workflow.attempt_count += 1
        workflow.resubmitted_at = now
        workflow.submission.submitted_at = now
        workflow.submission.save(update_fields=["submitted_at", "updated_at"])
    elif target_status == SubmissionWorkflow.MARKED:
        if not workflow.submission.marked_at:
            workflow.submission.marked_at = now
            workflow.submission.marked_by = actor
            workflow.submission.save(
                update_fields=["marked_at", "marked_by", "updated_at"]
            )

    workflow.status = target_status
    workflow.full_clean()
    workflow.save()
    return workflow


def workflow_validation_errors(obj) -> list[str]:
    try:
        obj.full_clean()
    except ValidationError as exc:
        return list(exc.messages)
    return []


def coursework_workflow_readiness() -> dict:
    activity_count = LearningActivity.objects.count()
    submission_count = AssignmentSubmission.objects.count()
    missing_profiles = LearningActivity.objects.filter(
        workflow_profile__isnull=True
    ).count()
    missing_workflows = AssignmentSubmission.objects.filter(
        workflow__isnull=True
    ).count()

    invalid_profiles = []
    for profile in LearningActivityProfile.objects.select_related(
        "activity",
        "activity__assignment",
        "activity__material",
    ):
        errors = workflow_validation_errors(profile)
        if errors:
            invalid_profiles.append({"profile": profile, "errors": errors})

    invalid_workflows = []
    for workflow in SubmissionWorkflow.objects.select_related(
        "submission",
        "submission__activity",
        "submission__activity__workflow_profile",
    ):
        errors = workflow_validation_errors(workflow)
        if errors:
            invalid_workflows.append({"workflow": workflow, "errors": errors})

    invalid_groups = []
    for group in AssignmentGroup.objects.select_related(
        "activity",
        "activity__workflow_profile",
    ):
        errors = workflow_validation_errors(group)
        if errors:
            invalid_groups.append({"group": group, "errors": errors})

    over_capacity_groups = 0
    for group in AssignmentGroup.objects.filter(
        is_active=True,
        capacity__isnull=False,
    ):
        if group.memberships.filter(is_active=True).count() > group.capacity:
            over_capacity_groups += 1

    invalid_group_submissions = []
    for submission in GroupSubmission.objects.select_related(
        "activity",
        "activity__workflow_profile",
        "group",
        "submitted_by",
    ):
        errors = workflow_validation_errors(submission)
        if errors:
            invalid_group_submissions.append(
                {"submission": submission, "errors": errors}
            )

    duplicate_active_memberships = 0
    for membership in AssignmentGroupMember.objects.filter(is_active=True).select_related(
        "group",
        "group__activity",
    ):
        duplicate_active_memberships += AssignmentGroupMember.objects.filter(
            is_active=True,
            student_id=membership.student_id,
            group__activity_id=membership.group.activity_id,
        ).exclude(pk=membership.pk).count()
    duplicate_active_memberships //= 2

    checks = {
        "profiles_complete": missing_profiles == 0,
        "submission_workflows_complete": missing_workflows == 0,
        "profiles_valid": not invalid_profiles,
        "submission_workflows_valid": not invalid_workflows,
        "groups_valid": not invalid_groups,
        "group_capacity_valid": over_capacity_groups == 0,
        "group_submissions_valid": not invalid_group_submissions,
        "one_group_per_activity": duplicate_active_memberships == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "activity_count": activity_count,
        "submission_count": submission_count,
        "missing_profile_count": missing_profiles,
        "missing_workflow_count": missing_workflows,
        "invalid_profile_count": len(invalid_profiles),
        "invalid_workflow_count": len(invalid_workflows),
        "invalid_group_count": len(invalid_groups),
        "over_capacity_group_count": over_capacity_groups,
        "invalid_group_submission_count": len(invalid_group_submissions),
        "duplicate_active_membership_count": duplicate_active_memberships,
        "invalid_profiles": invalid_profiles,
        "invalid_workflows": invalid_workflows,
        "invalid_groups": invalid_groups,
        "invalid_group_submissions": invalid_group_submissions,
    }
