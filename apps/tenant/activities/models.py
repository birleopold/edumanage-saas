import uuid

from django.conf import settings
from django.db import connection, models
from django.utils import timezone


def activities_upload_to(instance, filename: str) -> str:
    schema = getattr(connection, "schema_name", "public") or "public"
    return f"{schema}/activities/{filename}"


class Activity(models.Model):
    CLUB = "CLUB"
    SPORT = "SPORT"
    RELIGIOUS = "RELIGIOUS"
    CO_CURRICULAR = "CO_CURRICULAR"
    GENERAL = "GENERAL"

    TYPE_CHOICES = (
        (CLUB, "Club"),
        (SPORT, "Sport"),
        (RELIGIOUS, "Religious"),
        (CO_CURRICULAR, "Co-curricular"),
        (GENERAL, "General"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=GENERAL)
    description = models.TextField(blank=True)

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    head = models.ForeignKey(
        "hr.StaffProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_activities",
    )

    meeting_day = models.CharField(max_length=32, blank=True)
    meeting_time = models.CharField(max_length=32, blank=True)
    location = models.CharField(max_length=128, blank=True)

    poster = models.FileField(upload_to=activities_upload_to, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_activities",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class ActivityMember(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="memberships")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="activity_memberships")
    joined_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("activity", "student")
        ordering = ("-joined_at",)

    def __str__(self) -> str:
        return f"{self.activity} -> {self.student}"
