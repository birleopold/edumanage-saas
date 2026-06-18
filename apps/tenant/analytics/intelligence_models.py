from django.db import models
from django.utils import timezone


class AnalyticsRun(models.Model):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    RUN_TYPE_CHOICES = ((MANUAL, "Manual"), (SCHEDULED, "Scheduled"))
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STATUS_CHOICES = ((STARTED, "Started"), (SUCCESS, "Success"), (FAILED, "Failed"))

    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.SET_NULL, null=True, blank=True)
    run_type = models.CharField(max_length=16, choices=RUN_TYPE_CHOICES, default=MANUAL)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STARTED)
    generated_snapshots = models.PositiveIntegerField(default=0)
    generated_alerts = models.PositiveIntegerField(default=0)
    generated_teacher_metrics = models.PositiveIntegerField(default=0)
    generated_class_reports = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "analytics"
        ordering = ("-started_at",)

    def __str__(self):
        return f"Analytics run {self.id} - {self.status}"


class StudentRecommendation(models.Model):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"
    STATUS_CHOICES = ((OPEN, "Open"), (IN_PROGRESS, "In progress"), (COMPLETED, "Completed"), (DISMISSED, "Dismissed"))

    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="analytics_recommendations")
    snapshot = models.ForeignKey("analytics.StudentPerformanceSnapshot", on_delete=models.SET_NULL, null=True, blank=True, related_name="recommendations")
    alert = models.ForeignKey("analytics.AtRiskAlert", on_delete=models.SET_NULL, null=True, blank=True, related_name="recommendations")
    title = models.CharField(max_length=180)
    recommendation = models.TextField()
    subject = models.ForeignKey("academics.Course", on_delete=models.SET_NULL, null=True, blank=True)
    priority = models.CharField(max_length=16, default="MEDIUM")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "analytics"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "status"]), models.Index(fields=["priority", "status"])]

    def __str__(self):
        return f"{self.student} - {self.title}"


class Intervention(models.Model):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = ((PLANNED, "Planned"), (ACTIVE, "Active"), (COMPLETED, "Completed"), (CANCELLED, "Cancelled"))

    alert = models.ForeignKey("analytics.AtRiskAlert", on_delete=models.CASCADE, related_name="interventions")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="interventions")
    assigned_to = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="interventions")
    title = models.CharField(max_length=180)
    plan = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PLANNED)
    start_date = models.DateField(default=timezone.localdate)
    target_date = models.DateField(null=True, blank=True)
    progress_note = models.TextField(blank=True)
    outcome = models.TextField(blank=True)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "analytics"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "status"]), models.Index(fields=["alert", "status"])]

    def __str__(self):
        return f"{self.student} - {self.title}"


class ReportCardCommentSuggestion(models.Model):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="comment_suggestions")
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    snapshot = models.ForeignKey("analytics.StudentPerformanceSnapshot", on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField()
    strengths = models.JSONField(default=list, blank=True)
    weak_areas = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "analytics"
        ordering = ("-generated_at",)
        unique_together = ("student", "term")

    def __str__(self):
        return f"Comment suggestion - {self.student} - {self.term}"
