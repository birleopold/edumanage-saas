from django.conf import settings
from django.db import models


class Incident(models.Model):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

    STATUS_CHOICES = (
        (OPEN, "Open"),
        (RESOLVED, "Resolved"),
        (DISMISSED, "Dismissed"),
    )

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    SEVERITY_CHOICES = (
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
    )

    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    reported_by = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=64, blank=True)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default=MEDIUM)
    incident_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Incident #{self.id} - {self.title}"


class IncidentAction(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="actions")
    action = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    performed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return self.action
