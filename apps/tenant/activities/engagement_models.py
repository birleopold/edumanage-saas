import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .programme_models import ActivityAchievement, ActivitySession


def _token():
    return secrets.token_urlsafe(24)


class ActivityIncident(models.Model):
    CONDUCT = "CONDUCT"
    INJURY = "INJURY"
    SAFEGUARDING = "SAFEGUARDING"
    ATTENDANCE = "ATTENDANCE"
    EQUIPMENT = "EQUIPMENT"
    TRAVEL = "TRAVEL"
    OTHER = "OTHER"
    TYPE_CHOICES = (
        (CONDUCT, "Conduct"),
        (INJURY, "Injury"),
        (SAFEGUARDING, "Safeguarding"),
        (ATTENDANCE, "Attendance"),
        (EQUIPMENT, "Equipment or property"),
        (TRAVEL, "Travel or trip"),
        (OTHER, "Other"),
    )

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = (
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
        (CRITICAL, "Critical"),
    )

    OPEN = "OPEN"
    REVIEWING = "REVIEWING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    STATUS_CHOICES = (
        (OPEN, "Open"),
        (REVIEWING, "Under review"),
        (RESOLVED, "Resolved"),
        (CLOSED, "Closed"),
    )

    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="incidents",
    )
    session = models.ForeignKey(
        ActivitySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="activity_incidents",
    )
    incident_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default=LOW,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=OPEN,
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    summary = models.TextField()
    action_taken = models.TextField(blank=True)
    follow_up_at = models.DateTimeField(null=True, blank=True)
    confidential = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_incidents_recorded",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_incidents_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=("student", "status", "severity")),
        ]

    def __str__(self):
        return f"{self.student} — {self.activity} — {self.get_incident_type_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.session_id and self.session.activity_id != self.activity_id:
            errors["session"] = "The session must belong to the selected activity."
        if self.student_id and self.activity_id:
            if not self.activity.memberships.filter(
                student_id=self.student_id,
                is_active=True,
            ).exists():
                errors["student"] = "The learner is not an active member of this activity."
        if self.status in {self.RESOLVED, self.CLOSED}:
            if not self.resolved_at:
                errors["resolved_at"] = "Record when the incident was resolved."
            if not self.action_taken.strip():
                errors["action_taken"] = "Record the action taken."
        if errors:
            raise ValidationError(errors)


class ActivityCertificate(models.Model):
    achievement = models.OneToOneField(
        ActivityAchievement,
        on_delete=models.PROTECT,
        related_name="certificate",
    )
    reference = models.CharField(max_length=64, unique=True)
    verification_token = models.CharField(
        max_length=64,
        default=_token,
        unique=True,
        editable=False,
    )
    title = models.CharField(max_length=200)
    statement = models.TextField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_certificates_issued",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_certificates_revoked",
    )
    revocation_reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-issued_at",)

    def __str__(self):
        return f"{self.reference} — {self.achievement.membership.student}"

    @property
    def is_valid(self):
        return not self.is_revoked

    def clean(self):
        super().clean()
        if self.achievement_id and self.achievement.achievement_type not in {
            ActivityAchievement.AWARD,
            ActivityAchievement.MEDAL,
            ActivityAchievement.CERTIFICATE,
            ActivityAchievement.RECORD,
            ActivityAchievement.LEADERSHIP,
            ActivityAchievement.SERVICE,
            ActivityAchievement.PARTICIPATION,
        }:
            raise ValidationError({"achievement": "The achievement cannot issue a certificate."})
        if self.is_revoked:
            errors = {}
            if not self.revoked_at:
                errors["revoked_at"] = "Record the revocation time."
            if not self.revocation_reason.strip():
                errors["revocation_reason"] = "Record why the certificate was revoked."
            if errors:
                raise ValidationError(errors)
