from django.conf import settings
from django.db import models


class Grievance(models.Model):
    """
    Formal concern raised by staff or parents (separate from discipline incidents).
    """

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

    STATUS_CHOICES = (
        (OPEN, "Open"),
        (IN_PROGRESS, "In progress"),
        (RESOLVED, "Resolved"),
        (CLOSED, "Closed"),
    )

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grievances",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grievances_submitted",
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    resolution_notes = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grievances_handled",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.subject} ({self.get_status_display()})"
