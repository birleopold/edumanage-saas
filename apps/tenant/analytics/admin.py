from django.contrib import admin

from .models import (
    AtRiskAlert,
    ClassPerformanceReport,
    PerformanceTrend,
    StudentPerformanceSnapshot,
    SubjectPerformance,
    TeacherPerformanceMetrics,
)


@admin.register(StudentPerformanceSnapshot)
class StudentPerformanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("student", "term", "gpa", "overall_percentage", "class_rank", "is_at_risk", "risk_level", "generated_at")
    list_filter = ("term", "is_at_risk", "risk_level", "performance_trend")
    search_fields = ("student__first_name", "student__last_name", "student__student_id")
    readonly_fields = ("generated_at", "updated_at")
    date_hierarchy = "generated_at"


@admin.register(SubjectPerformance)
class SubjectPerformanceAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "course", "final_score", "percentage", "grade", "subject_rank", "is_passed", "is_weak_area")
    list_filter = ("is_passed", "is_weak_area", "snapshot__term")
    search_fields = ("snapshot__student__first_name", "snapshot__student__last_name", "course__name")
    readonly_fields = ("created_at",)


@admin.register(ClassPerformanceReport)
class ClassPerformanceReportAdmin(admin.ModelAdmin):
    list_display = ("stream", "term", "total_students", "average_gpa", "average_percentage", "at_risk_count", "generated_at")
    list_filter = ("term", "stream")
    search_fields = ("stream__name", "stream__class_group__name")
    readonly_fields = ("generated_at", "updated_at")
    date_hierarchy = "generated_at"


@admin.register(TeacherPerformanceMetrics)
class TeacherPerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ("teacher", "course", "term", "total_students", "average_student_score", "pass_rate", "excellence_rate")
    list_filter = ("term", "course", "performance_trend")
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "course__name")
    readonly_fields = ("generated_at", "updated_at")


@admin.register(PerformanceTrend)
class PerformanceTrendAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "term", "score", "percentage", "grade", "gpa", "rank")
    list_filter = ("term", "course")
    search_fields = ("student__first_name", "student__last_name", "course__name")
    readonly_fields = ("recorded_at",)


@admin.register(AtRiskAlert)
class AtRiskAlertAdmin(admin.ModelAdmin):
    list_display = ("student", "severity", "status", "title", "assigned_to", "created_at")
    list_filter = ("severity", "status", "created_at")
    search_fields = ("student__first_name", "student__last_name", "title", "description")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    fieldsets = (
        ("Alert Information", {
            "fields": ("student", "snapshot", "severity", "title", "description", "risk_factors", "recommended_actions")
        }),
        ("Status & Assignment", {
            "fields": ("status", "assigned_to", "acknowledged_by", "acknowledged_at", "resolved_at", "resolution_notes")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at")
        }),
    )
