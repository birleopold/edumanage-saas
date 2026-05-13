from django.conf import settings
from django.db import models
from django.utils import timezone


class ParentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_profile",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    allow_sms_alerts = models.BooleanField(
        default=True,
        help_text="Parent consents to receive SMS alerts and reminders.",
    )
    allow_whatsapp_alerts = models.BooleanField(
        default=True,
        help_text="Parent consents to receive WhatsApp alerts and reminders.",
    )
    communication_consent_updated_at = models.DateTimeField(
        default=timezone.now,
        help_text="Last time communication consent settings were updated.",
    )
    results_access_pin_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Hashed PIN for viewing children's published results in the parent portal.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("last_name", "first_name")

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()


class ParentStudentLink(models.Model):
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    relationship = models.CharField(max_length=64, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("parent", "student")

    def __str__(self) -> str:
        return f"{self.parent} -> {self.student}"
