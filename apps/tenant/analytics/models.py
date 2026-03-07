from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class StudentPerformanceSnapshot(models.Model):
    """Periodic snapshot of student performance metrics"""
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="performance_snapshots")
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    stream = models.ForeignKey("academics.Stream", on_delete=models.SET_NULL, null=True, blank=True)
    
    # Academic Metrics
    gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Grade Point Average")
    overall_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_subjects = models.PositiveIntegerField(default=0)
    subjects_passed = models.PositiveIntegerField(default=0)
    subjects_failed = models.PositiveIntegerField(default=0)
    
    # Rankings
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    class_size = models.PositiveIntegerField(null=True, blank=True)
    stream_rank = models.PositiveIntegerField(null=True, blank=True)
    stream_size = models.PositiveIntegerField(null=True, blank=True)
    percentile = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Percentile in class")
    
    # Trend Analysis
    performance_trend = models.CharField(max_length=16, blank=True, help_text="IMPROVING, DECLINING, STABLE")
    previous_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    gpa_change = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Risk Assessment
    is_at_risk = models.BooleanField(default=False)
    risk_level = models.CharField(max_length=16, blank=True, help_text="LOW, MEDIUM, HIGH, CRITICAL")
    risk_factors = models.JSONField(default=list, help_text="List of identified risk factors")
    
    # Attendance & Behavior
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discipline_incidents = models.PositiveIntegerField(default=0)
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ("-term__year__name", "term__order", "student")
        unique_together = ("student", "term")
        indexes = [
            models.Index(fields=["student", "-term"]),
            models.Index(fields=["is_at_risk"]),
            models.Index(fields=["risk_level"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.student} - {self.term}"
    
    def calculate_percentile(self):
        """Calculate student's percentile in class"""
        if self.class_rank and self.class_size:
            self.percentile = ((self.class_size - self.class_rank + 1) / self.class_size) * 100
            self.save()


class SubjectPerformance(models.Model):
    """Track performance in individual subjects"""
    snapshot = models.ForeignKey(StudentPerformanceSnapshot, on_delete=models.CASCADE, related_name="subject_performances")
    course = models.ForeignKey("academics.Course", on_delete=models.CASCADE)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE, null=True, blank=True)
    
    # Scores
    assessment_average = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    exam_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    final_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=8, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    
    # Rankings
    subject_rank = models.PositiveIntegerField(null=True, blank=True)
    total_students = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    is_passed = models.BooleanField(default=False)
    is_weak_area = models.BooleanField(default=False, help_text="Performance below expected threshold")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ("snapshot", "course")
        unique_together = ("snapshot", "course")
    
    def __str__(self) -> str:
        return f"{self.snapshot.student} - {self.course}"


class ClassPerformanceReport(models.Model):
    """Aggregated performance report for a class/stream"""
    stream = models.ForeignKey("academics.Stream", on_delete=models.CASCADE, related_name="performance_reports")
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    
    # Overall Statistics
    total_students = models.PositiveIntegerField(default=0)
    average_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    average_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    median_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    highest_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    lowest_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Performance Distribution
    students_excellent = models.PositiveIntegerField(default=0, help_text="GPA >= 3.5")
    students_good = models.PositiveIntegerField(default=0, help_text="3.0 <= GPA < 3.5")
    students_average = models.PositiveIntegerField(default=0, help_text="2.5 <= GPA < 3.0")
    students_below_average = models.PositiveIntegerField(default=0, help_text="2.0 <= GPA < 2.5")
    students_failing = models.PositiveIntegerField(default=0, help_text="GPA < 2.0")
    
    # At-Risk Students
    at_risk_count = models.PositiveIntegerField(default=0)
    critical_risk_count = models.PositiveIntegerField(default=0)
    
    # Subject Performance
    best_performing_subjects = models.JSONField(default=list, help_text="Top 3 subjects by average")
    worst_performing_subjects = models.JSONField(default=list, help_text="Bottom 3 subjects by average")
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ("-term__year__name", "term__order", "stream")
        unique_together = ("stream", "term")
    
    def __str__(self) -> str:
        return f"{self.stream} - {self.term}"


class TeacherPerformanceMetrics(models.Model):
    """Performance metrics for teachers based on student outcomes"""
    teacher = models.ForeignKey("teachers.TeacherProfile", on_delete=models.CASCADE, related_name="performance_metrics")
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    course = models.ForeignKey("academics.Course", on_delete=models.SET_NULL, null=True, blank=True)
    
    # Student Performance
    total_students = models.PositiveIntegerField(default=0)
    average_student_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    excellence_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="% scoring >= 80%")
    
    # Assessment Activity
    total_assessments = models.PositiveIntegerField(default=0)
    assessments_published = models.PositiveIntegerField(default=0)
    average_grading_time_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Improvement Trends
    performance_trend = models.CharField(max_length=16, blank=True)
    previous_average = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    score_improvement = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Comparative Metrics
    department_rank = models.PositiveIntegerField(null=True, blank=True)
    above_department_average = models.BooleanField(default=False)
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ("-term__year__name", "term__order", "teacher")
        unique_together = ("teacher", "term", "course")
    
    def __str__(self) -> str:
        if self.course:
            return f"{self.teacher} - {self.course} - {self.term}"
        return f"{self.teacher} - {self.term}"


class PerformanceTrend(models.Model):
    """Historical trend data for visualizations"""
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="performance_trends")
    course = models.ForeignKey("academics.Course", on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    
    # Metrics
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=8, blank=True)
    gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadata
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ("student", "term__year__name", "term__order", "course")
        indexes = [
            models.Index(fields=["student", "term"]),
            models.Index(fields=["course", "term"]),
        ]
    
    def __str__(self) -> str:
        if self.course:
            return f"{self.student} - {self.course} - {self.term}"
        return f"{self.student} - Overall - {self.term}"


class AtRiskAlert(models.Model):
    """Alerts for at-risk students requiring intervention"""
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
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    
    STATUS_CHOICES = (
        (OPEN, "Open"),
        (ACKNOWLEDGED, "Acknowledged"),
        (IN_PROGRESS, "In Progress"),
        (RESOLVED, "Resolved"),
        (DISMISSED, "Dismissed"),
    )
    
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="risk_alerts")
    snapshot = models.ForeignKey(StudentPerformanceSnapshot, on_delete=models.CASCADE, null=True, blank=True)
    
    # Alert Details
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES)
    risk_factors = models.JSONField(default=list)
    title = models.CharField(max_length=255)
    description = models.TextField()
    recommended_actions = models.TextField(blank=True)
    
    # Status Tracking
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    assigned_to = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_alerts")
    acknowledged_by = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="acknowledged_alerts")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ("-created_at", "-severity")
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["severity", "status"]),
            models.Index(fields=["-created_at"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.get_severity_display()} - {self.student} - {self.title}"
