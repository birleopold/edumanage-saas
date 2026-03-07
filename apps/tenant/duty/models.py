import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TeacherDutyRoster(models.Model):
    MORNING = "MORNING"
    EVENING = "EVENING"
    WEEKEND = "WEEKEND"
    GENERAL = "GENERAL"

    DUTY_TYPE_CHOICES = (
        (MORNING, "Morning"),
        (EVENING, "Evening"),
        (WEEKEND, "Weekend"),
        (GENERAL, "General"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    date = models.DateField(default=timezone.localdate)
    duty_type = models.CharField(max_length=32, choices=DUTY_TYPE_CHOICES, default=GENERAL)
    teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="duty_rosters",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_duty_rosters",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date",)
        unique_together = ("teacher", "date", "duty_type")

    def __str__(self) -> str:
        return f"{self.date} - {self.teacher} ({self.duty_type})"
