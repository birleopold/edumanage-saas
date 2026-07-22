from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .candidate_readiness import (
    assert_candidate_readiness,
    record_candidate_readiness,
)
from .models import CandidateDossier


PROTECTED_STATUSES = {
    CandidateDossier.READY,
    CandidateDossier.SUBMITTED,
    CandidateDossier.APPROVED,
}


@receiver(pre_save, sender=CandidateDossier)
def block_unready_candidate_transition(sender, instance, **kwargs):
    if instance.registration_status not in PROTECTED_STATUSES:
        return
    previous_status = None
    if instance.pk:
        previous_status = (
            CandidateDossier.objects.filter(pk=instance.pk)
            .values_list("registration_status", flat=True)
            .first()
        )
    if previous_status == instance.registration_status:
        return
    assert_candidate_readiness(
        instance,
        target_status=instance.registration_status,
    )


@receiver(post_save, sender=CandidateDossier)
def snapshot_candidate_readiness(sender, instance, created, **kwargs):
    if instance.registration_status not in PROTECTED_STATUSES:
        return
    record_candidate_readiness(
        instance,
        actor=instance.verified_by,
        target_status=instance.registration_status,
    )
