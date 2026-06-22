from dataclasses import dataclass

from django.contrib import messages
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.portals.permissions import admin_portal_required

from .models import (
    AtRiskAlert,
    ClassPerformanceReport,
    PerformanceTrend,
    StudentPerformanceSnapshot,
    SubjectPerformance,
    TeacherPerformanceMetrics,
)


@dataclass(frozen=True)
class AnalyticsRecordConfig:
    slug: str
    label: str
    description: str
    model: object
    icon: str
    display_fields: tuple[str, ...]


ANALYTICS_RECORDS = {
    "at-risk-alerts": AnalyticsRecordConfig(
        slug="at-risk-alerts",
        label="At Risk Alerts",
        description="Identify students needing support and track intervention actions.",
        model=AtRiskAlert,
        icon="ph-warning-circle",
        display_fields=("student", "severity", "status", "title", "created_at"),
    ),
    "class-performance-reports": AnalyticsRecordConfig(
        slug="class-performance-reports",
        label="Class Performance Reports",
        description="Review class and stream performance summaries by academic term.",
        model=ClassPerformanceReport,
        icon="ph-chart-bar",
        display_fields=("stream", "term", "total_students", "average_percentage", "at_risk_count"),
    ),
    "performance-trends": AnalyticsRecordConfig(
        slug="performance-trends",
        label="Performance Trends",
        description="Track historical student performance movement over time.",
        model=PerformanceTrend,
        icon="ph-trend-up",
        display_fields=("student", "course", "term", "percentage", "grade"),
    ),
    "student-performance-snapshots": AnalyticsRecordConfig(
        slug="student-performance-snapshots",
        label="Student Performance Snapshots",
        description="Store termly student academic, ranking, attendance and risk snapshots.",
        model=StudentPerformanceSnapshot,
        icon="ph-student",
        display_fields=("student", "term", "overall_percentage", "performance_trend", "risk_level"),
    ),
    "subject-performances": AnalyticsRecordConfig(
        slug="subject-performances",
        label="Subject Performances",
        description="Track performance per subject or course for each student snapshot.",
        model=SubjectPerformance,
        icon="ph-books",
        display_fields=("snapshot", "course", "percentage", "grade", "is_weak_area"),
    ),
    "teacher-performance-metrics": AnalyticsRecordConfig(
        slug="teacher-performance-metrics",
        label="Teacher Performance Metrics",
        description="Review teacher outcome indicators such as pass rate, excellence rate and grading activity.",
        model=TeacherPerformanceMetrics,
        icon="ph-chalkboard-teacher",
        display_fields=("teacher", "term", "course", "average_student_score", "pass_rate"),
    ),
}


def _get_config(slug: str) -> AnalyticsRecordConfig:
    return get_object_or_404_config(slug)


def get_object_or_404_config(slug: str) -> AnalyticsRecordConfig:
    config = ANALYTICS_RECORDS.get(slug)
    if not config:
        raise ValueError("Unknown analytics record type")
    return config


def _display_value(obj, field_name: str):
    value = getattr(obj, field_name, "")
    if callable(value):
        value = value()
    return value if value not in (None, "") else "-"


@admin_portal_required
def analytics_records_setup(request):
    items = []
    for config in ANALYTICS_RECORDS.values():
        items.append(
            {
                "label": config.label,
                "description": config.description,
                "icon": config.icon,
                "count": config.model.objects.count(),
                "list_url": reverse("admin_analytics_records_list", kwargs={"slug": config.slug}),
                "add_url": reverse("admin_analytics_records_create", kwargs={"slug": config.slug}),
            }
        )
    return render(request, "portals/admin/analytics/records_setup.html", {"items": items})


@admin_portal_required
def analytics_records_list(request, slug):
    config = _get_config(slug)
    qs = config.model.objects.all()[:200]
    rows = []
    for obj in qs:
        rows.append(
            {
                "object": obj,
                "values": [_display_value(obj, field) for field in config.display_fields],
                "edit_url": reverse("admin_analytics_records_edit", kwargs={"slug": slug, "pk": obj.pk}),
            }
        )
    return render(
        request,
        "portals/admin/analytics/record_list.html",
        {"config": config, "fields": config.display_fields, "rows": rows},
    )


@admin_portal_required
def analytics_records_create(request, slug):
    config = _get_config(slug)
    FormClass = modelform_factory(config.model, fields="__all__")
    form = FormClass(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{config.label} record added successfully.")
        return redirect("admin_analytics_records_list", slug=slug)
    return render(request, "portals/admin/analytics/record_form.html", {"config": config, "form": form, "mode": "Add"})


@admin_portal_required
def analytics_records_edit(request, slug, pk):
    config = _get_config(slug)
    obj = get_object_or_404(config.model, pk=pk)
    FormClass = modelform_factory(config.model, fields="__all__")
    form = FormClass(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{config.label} record updated successfully.")
        return redirect("admin_analytics_records_list", slug=slug)
    return render(request, "portals/admin/analytics/record_form.html", {"config": config, "form": form, "mode": "Edit", "object": obj})
