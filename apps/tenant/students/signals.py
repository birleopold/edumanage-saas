from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentProfile
from .services import sync_student_user


@receiver(post_save, sender=StudentProfile)
def synchronize_linked_student_account(sender, instance, **kwargs):
    """Keep the login account aligned after imports, creation and edits."""

    sync_student_user(instance)


@receiver(user_logged_in)
def synchronize_student_account_on_login(sender, user, **kwargs):
    """Repair older student accounts as soon as the learner signs in."""

    student = StudentProfile.objects.filter(user=user).select_related("user").first()
    if student:
        sync_student_user(student)
