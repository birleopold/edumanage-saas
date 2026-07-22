from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Assessment, AssessmentScore, AssessmentType
from .policy_models import AssessmentPolicy, AssessmentScorePolicy


@receiver(post_save, sender=Assessment)
def ensure_assessment_policy(sender, instance, created, **kwargs):
    grading_mode = AssessmentPolicy.NUMERIC
    if (
        instance.assessment_type_id
        and instance.assessment_type.kind == AssessmentType.COMPETENCY
    ):
        grading_mode = AssessmentPolicy.COMPETENCY
    defaults = {
        "grading_mode": grading_mode,
        "responsible_teacher_id": instance.offering.teacher_id,
    }
    policy, policy_created = AssessmentPolicy.objects.get_or_create(
        assessment=instance,
        defaults=defaults,
    )
    if not policy_created and not policy.responsible_teacher_id and instance.offering.teacher_id:
        policy.responsible_teacher_id = instance.offering.teacher_id
        policy.save(update_fields=["responsible_teacher", "updated_at"])


@receiver(post_save, sender=AssessmentScore)
def ensure_assessment_score_policy(sender, instance, **kwargs):
    AssessmentScorePolicy.objects.get_or_create(score_record=instance)
