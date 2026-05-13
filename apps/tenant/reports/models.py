from django.conf import settings
from django.db import models


class ReportRun(models.Model):
    """Log of generated report files (e.g. cron / manual run)."""

    OVERVIEW_CSV = "overview_csv"

    TYPE_CHOICES = ((OVERVIEW_CSV, "Operational overview (CSV)"),)

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    report_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=OVERVIEW_CSV)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_runs",
    )
    file_path = models.CharField(max_length=512, blank=True, help_text="Relative to MEDIA_ROOT.")
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.report_type} @ {self.created_at} ({self.status})"
