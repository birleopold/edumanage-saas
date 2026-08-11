from django.conf import settings
from django.core.exceptions import ValidationError
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


class TermReportRemark(models.Model):
    """Consolidated school remarks attached to one learner's term report."""

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="term_report_remarks",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="term_report_remarks",
    )
    term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.CASCADE,
        related_name="student_report_remarks",
    )
    class_teacher_comment = models.TextField(blank=True)
    head_comment = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_term_report_remarks",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name", "student__student_id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "term"),
                name="uniq_student_term_report_remark",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student} — {self.term}"

    def clean(self):
        super().clean()
        if self.campus_id and self.student_id and self.student.campus_id:
            if self.campus_id != self.student.campus_id:
                raise ValidationError({"campus": "Report remark campus must match the learner's campus."})

    def save(self, *args, **kwargs):
        if not self.campus_id and self.student_id:
            self.campus_id = self.student.campus_id
        self.full_clean()
        super().save(*args, **kwargs)
