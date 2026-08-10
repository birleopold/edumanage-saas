from django.contrib.auth.signals import user_logged_in
from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_tenants.utils import get_public_schema_name

from .models import StudentProfile
from .services import sync_student_user_identity


@receiver(post_save, sender=StudentProfile)
def synchronize_student_login_identity(sender, instance, **kwargs):
    """Mirror the authoritative student identity into the linked login user."""

    if instance.user_id:
        sync_student_user_identity(instance)


@receiver(user_logged_in)
def synchronize_student_identity_on_login(sender, request, user, **kwargs):
    """Repair older student accounts before the first tenant portal page renders.

    In PostgreSQL SaaS mode, platform authentication runs in the public schema,
    where tenant-only student tables intentionally do not exist. Local SQLite
    development has no tenant search path, so it should still perform the same
    identity repair against the local student table.
    """

    if getattr(user, "is_superuser", False):
        return

    schema_name = getattr(connection, "schema_name", None)
    if connection.vendor == "postgresql" and schema_name == get_public_schema_name():
        return

    student = StudentProfile.objects.filter(user=user).first()
    if student:
        sync_student_user_identity(student)
