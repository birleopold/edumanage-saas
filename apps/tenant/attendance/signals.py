from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import AttendanceEvent
from .payload_privacy import scrub_attendance_payload


@receiver(pre_save, sender=AttendanceEvent)
def scrub_attendance_event_raw_payload(sender, instance, **kwargs):
    """Prevent biometric enrollment material from entering the event ledger."""

    instance.raw_payload = scrub_attendance_payload(instance.raw_payload or {})
