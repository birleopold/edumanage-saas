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
    digest_enabled = models.BooleanField(
        default=True,
        help_text="Parent should receive Smart Parent Digest summaries.",
    )
    digest_email_enabled = models.BooleanField(
        default=False,
        help_text="Email Smart Parent Digest summaries when an email address is available.",
    )
    digest_whatsapp_enabled = models.BooleanField(
        default=False,
        help_text="Send Smart Parent Digest summaries on WhatsApp when consent and phone number are available.",
    )
    digest_pwa_enabled = models.BooleanField(
        default=True,
        help_text="Send Smart Parent Digest browser/PWA alerts when subscriptions are available.",
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


class ParentDigest(models.Model):
    CREATED = "CREATED"
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    STATUS_CHOICES = (
        (CREATED, "Created"),
        (SENT, "Sent"),
        (SKIPPED, "Skipped"),
    )

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="digests")
    window_start = models.DateField()
    window_end = models.DateField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    totals = models.JSONField(default=dict, blank=True)
    channels = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=CREATED)
    notification = models.ForeignKey(
        "orgsettings.Notification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_digests",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_parent_digests",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-window_end", "-created_at")
        unique_together = ("parent", "window_start", "window_end")
        indexes = [
            models.Index(fields=["parent", "window_start", "window_end"]),
            models.Index(fields=["status", "sent_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.parent} digest {self.window_start} - {self.window_end}"
