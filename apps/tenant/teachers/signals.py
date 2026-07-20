from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenant.hr.models import StaffProfile

from .models import TeacherProfile
from .sync import ensure_staff_for_teacher, ensure_teacher_for_staff, synchronization_in_progress


@receiver(post_save, sender=StaffProfile, dispatch_uid="normalize_staff_to_teacher_profile")
def normalize_staff_to_teacher_profile(sender, instance, **kwargs):
    if synchronization_in_progress():
        return
    ensure_teacher_for_staff(instance)


@receiver(post_save, sender=TeacherProfile, dispatch_uid="normalize_teacher_to_staff_profile")
def normalize_teacher_to_staff_profile(sender, instance, **kwargs):
    if synchronization_in_progress():
        return
    ensure_staff_for_teacher(instance)
