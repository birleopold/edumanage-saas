from django.db.models.signals import post_save
from django.dispatch import receiver

from .activity_services import learning_activity_for_source, sync_learning_activity
from .models import Assignment, AssignmentSubmission, CourseworkComment, CourseworkProgress, LearningMaterial


@receiver(post_save, sender=LearningMaterial)
def sync_material_activity(sender, instance, raw=False, **kwargs):
    if not raw:
        sync_learning_activity(instance)


@receiver(post_save, sender=Assignment)
def sync_assignment_activity(sender, instance, raw=False, **kwargs):
    if not raw:
        sync_learning_activity(instance)


@receiver(post_save, sender=AssignmentSubmission)
def link_submission_activity(sender, instance, raw=False, **kwargs):
    if raw or instance.activity_id:
        return
    activity = learning_activity_for_source(instance.assignment)
    if activity:
        sender.objects.filter(pk=instance.pk, activity__isnull=True).update(activity=activity)


@receiver(post_save, sender=CourseworkComment)
def link_comment_activity(sender, instance, raw=False, **kwargs):
    if raw or instance.activity_id:
        return
    source = instance.material or instance.assignment
    activity = learning_activity_for_source(source)
    if activity:
        sender.objects.filter(pk=instance.pk, activity__isnull=True).update(activity=activity)


@receiver(post_save, sender=CourseworkProgress)
def link_progress_activity(sender, instance, raw=False, **kwargs):
    if raw or instance.activity_id:
        return
    source = instance.material or instance.assignment
    activity = learning_activity_for_source(source)
    if activity:
        sender.objects.filter(pk=instance.pk, activity__isnull=True).update(activity=activity)
