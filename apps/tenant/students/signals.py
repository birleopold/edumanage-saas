from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentProfile
from .services import sync_student_user


@receiver(post_save, sender=StudentProfile)
def synchronize_linked_student_account(sender, instance, **kwargs):
    """Keep the login account aligned after imports, creation and edits."""

    sync_student_user(instance)
