from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentProfile
from .services import sync_student_user_identity


@receiver(post_save, sender=StudentProfile)
def synchronize_student_login_identity(sender, instance, **kwargs):
    """Mirror the authoritative student identity into the linked login user."""

    if instance.user_id:
        sync_student_user_identity(instance)


@receiver(user_logged_in)
def synchronize_student_identity_on_login(sender, request, user, **kwargs):
    """Repair older student accounts before the first portal page is rendered."""

    student = StudentProfile.objects.filter(user=user).first()
    if student:
        sync_student_user_identity(student)
