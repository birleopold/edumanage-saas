from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import AttendanceDevice, AttendanceEvent, AttendanceIdentity
from .payload_privacy import scrub_attendance_payload


@receiver(pre_save, sender=AttendanceEvent)
def scrub_attendance_event_raw_payload(sender, instance, **kwargs):
    """Prevent biometric enrollment material from entering the event ledger."""

    instance.raw_payload = scrub_attendance_payload(instance.raw_payload or {})


@receiver(pre_save, sender=AttendanceDevice)
def protect_device_identity_namespace_scope(sender, instance, **kwargs):
    """Keep campus-bound device namespaces from crossing campus boundaries."""

    namespace = str(instance.identity_namespace or "").strip()
    if not namespace or not instance.campus_id:
        return

    conflicting_device = (
        AttendanceDevice.objects.filter(identity_namespace=namespace)
        .exclude(pk=instance.pk)
        .exclude(campus_id=instance.campus_id)
        .exists()
    )
    if conflicting_device:
        raise ValidationError(
            {"identity_namespace": "A campus-bound attendance namespace cannot be shared with another campus or a global device."}
        )

    conflicting_identity = AttendanceIdentity.objects.filter(namespace=namespace, is_active=True).filter(
        (Q(student__isnull=False) & ~Q(student__campus_id=instance.campus_id))
        | (Q(staff__isnull=False) & ~Q(staff__campus_id=instance.campus_id))
    )
    if conflicting_identity.exists():
        raise ValidationError(
            {"identity_namespace": "This namespace already contains a person mapping outside the selected campus."}
        )


@receiver(pre_save, sender=AttendanceIdentity)
def protect_identity_namespace_scope(sender, instance, **kwargs):
    """Reject person mappings that contradict campus-bound devices using a namespace."""

    namespace = str(instance.namespace or "").strip()
    if not namespace:
        return
    target = instance.student if instance.student_id else instance.staff if instance.staff_id else None
    if target is None:
        return
    target_campus_id = getattr(target, "campus_id", None)

    scoped_campus_ids = set(
        AttendanceDevice.objects.filter(
            identity_namespace=namespace,
            is_active=True,
            campus__isnull=False,
        ).values_list("campus_id", flat=True)
    )
    if scoped_campus_ids and (target_campus_id is None or scoped_campus_ids != {target_campus_id}):
        raise ValidationError(
            {"namespace": "This device namespace is scoped to a different campus than the selected person."}
        )
