from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AssignmentSubmission, LearningActivity
from .workflow_models import LearningActivityProfile, SubmissionWorkflow


KIND_MAP = {
    LearningActivity.RESOURCE: LearningActivityProfile.RESOURCE,
    LearningActivity.ASSIGNMENT: LearningActivityProfile.ASSIGNMENT,
    LearningActivity.PROJECT: LearningActivityProfile.PROJECT,
    LearningActivity.PRACTICAL: LearningActivityProfile.PRACTICAL,
    LearningActivity.DISCUSSION: LearningActivityProfile.DISCUSSION,
    LearningActivity.LIVE_CLASS: LearningActivityProfile.LIVE_CLASS,
    LearningActivity.VIDEO: LearningActivityProfile.VIDEO,
    LearningActivity.QUIZ: LearningActivityProfile.QUIZ,
    LearningActivity.OTHER: LearningActivityProfile.OTHER,
}


@receiver(post_save, sender=LearningActivity)
def ensure_learning_activity_profile(sender, instance, **kwargs):
    detailed_kind = KIND_MAP.get(instance.kind, LearningActivityProfile.OTHER)
    LearningActivityProfile.objects.get_or_create(
        activity=instance,
        defaults={"detailed_kind": detailed_kind},
    )


@receiver(post_save, sender=AssignmentSubmission)
def ensure_submission_workflow(sender, instance, **kwargs):
    workflow, created = SubmissionWorkflow.objects.get_or_create(
        submission=instance,
    )
    status = workflow.status
    is_late = workflow.is_late
    first_submitted_at = workflow.first_submitted_at

    if instance.marked_at:
        status = SubmissionWorkflow.MARKED
    elif instance.submitted_at:
        if first_submitted_at is None:
            first_submitted_at = instance.submitted_at
        due_at = instance.assignment.due_date
        is_late = bool(due_at and instance.submitted_at > due_at)
        if workflow.late_excused and is_late:
            status = SubmissionWorkflow.EXCUSED_LATE
        elif is_late:
            status = SubmissionWorkflow.LATE
        elif status in {
            SubmissionWorkflow.RESUBMISSION_REQUIRED,
            SubmissionWorkflow.RETURNED,
        }:
            status = SubmissionWorkflow.RESUBMITTED
        elif status == SubmissionWorkflow.DRAFT:
            status = SubmissionWorkflow.SUBMITTED
    elif created:
        status = SubmissionWorkflow.DRAFT

    changed = []
    if workflow.status != status:
        workflow.status = status
        changed.append("status")
    if workflow.is_late != is_late:
        workflow.is_late = is_late
        changed.append("is_late")
    if workflow.first_submitted_at != first_submitted_at:
        workflow.first_submitted_at = first_submitted_at
        changed.append("first_submitted_at")
    if changed:
        changed.append("updated_at")
        workflow.save(update_fields=changed)
