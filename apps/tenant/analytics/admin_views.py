import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, ClassGroup, Course, Stream
from apps.tenant.finance.models import Invoice
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import (
    AtRiskAlert,
    ClassPerformanceReport,
    PerformanceTrend,
    StudentPerformanceSnapshot,
    SubjectPerformance,
    TeacherPerformanceMetrics,
)
from .utils import (
    calculate_student_performance_snapshot,
    calculate_teacher_performance_metrics,
    export_student_performance_report,
    generate_class_performance_report,
)
from .risk_radar import build_student_risk_radar


def _parse_per_page(request, default=25):
    try:
        per_page = int(request.GET.get("per_page", default))
        return min(per_page, 100)
    except (ValueError, TypeError):
        return default


def _student_queryset_for(user):
    qs = StudentProfile.objects.filter(is_active=True)
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _snapshot_queryset_for(user):
    qs = StudentPerformanceSnapshot.objects.select_related("student", "stream", "term")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(student__campus=scoped)
    return qs


def _stream_queryset_for(user):
    qs = Stream.objects.filter(is_active=True).select_related("class_group")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(class_group__campus=scoped)
    return qs


def _class_report_queryset_for(user):
    qs = ClassPerformanceReport.objects.select_related("stream", "term")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(stream__class_group__campus=scoped)
    return qs


def _alert_queryset_for(user):
    qs = AtRiskAlert.objects.select_related("student", "assigned_to", "snapshot__term")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(student__campus=scoped)
    return qs


def _teacher_queryset_for(user):
    qs = TeacherProfile.objects.filter(user__is_active=True).select_related("user")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


@admin_portal_required
def charts_overview(request):
    """Visual charts (Chart.js) for headcount and billing mix."""
    return render(request, "portals/admin/analytics/charts_overview.html", {})


@admin_portal_required
def charts_overview_data(request):
    scoped = get_user_campus_scope(request.user)

    students = StudentProfile.objects.filter(is_active=True)
    if scoped:
        students = students.filter(campus=scoped)
    by_campus = list(
        students.values("campus__name").annotate(c=Count("id")).order_by("-c")[:20]
    )
    labels = [(row["campus__name"] or "Unassigned")[:40] for row in by_campus]
    counts = [row["c"] for row in by_campus]

    inv = Invoice.objects.all()
    if scoped:
        inv = inv.filter(student__campus=scoped)
    status_rows = list(inv.values("status").annotate(c=Count("id")).order_by("-c"))
    inv_labels = [r["status"] for r in status_rows]
    inv_counts = [r["c"] for r in status_rows]

    teachers = TeacherProfile.objects.filter(is_active=True)
    if scoped:
        teachers = teachers.filter(campus=scoped)

    return JsonResponse(
        {
            "students_by_campus": {"labels": labels, "counts": counts},
            "invoices_by_status": {"labels": inv_labels, "counts": inv_counts},
            "summary": {
                "students": students.count(),
                "teachers": teachers.count(),
                "invoices": inv.count(),
            },
        }
    )


@admin_portal_required
def analytics_dashboard(request):
    """Main analytics dashboard with overview metrics"""
    current_term = AcademicTerm.objects.filter(is_current=True).first()
    
    if not current_term:
        messages.warning(request, "No current academic term is set. Please configure the academic term.")
        return render(request, "portals/admin/analytics/dashboard.html", {})
    
    # Overall statistics
    total_students = _student_queryset_for(request.user).count()
    
    snapshots = _snapshot_queryset_for(request.user).filter(term=current_term)
    
    stats = {
        "total_students": total_students,
        "average_gpa": snapshots.aggregate(avg=Avg("gpa"))["avg"],
        "at_risk_count": snapshots.filter(is_at_risk=True).count(),
        "critical_risk_count": snapshots.filter(risk_level="CRITICAL").count(),
        "excellent_students": snapshots.filter(gpa__gte=Decimal(3.5)).count(),
    }
    
    # Performance distribution
    distribution = {
        "excellent": snapshots.filter(gpa__gte=Decimal(3.5)).count(),
        "good": snapshots.filter(gpa__gte=Decimal(3.0), gpa__lt=Decimal(3.5)).count(),
        "average": snapshots.filter(gpa__gte=Decimal(2.5), gpa__lt=Decimal(3.0)).count(),
        "below_average": snapshots.filter(gpa__gte=Decimal(2.0), gpa__lt=Decimal(2.5)).count(),
        "failing": snapshots.filter(gpa__lt=Decimal(2.0)).count(),
    }
    
    # Recent at-risk alerts
    recent_alerts = _alert_queryset_for(request.user).filter(
        status__in=["OPEN", "ACKNOWLEDGED"]
    ).order_by("-created_at")[:10]
    
    # Top performing classes
    class_reports = _class_report_queryset_for(request.user).filter(
        term=current_term
    ).order_by("-average_gpa")[:5]
    
    # Terms for dropdown
    terms = AcademicTerm.objects.all()[:10]
    
    context = {
        "current_term": current_term,
        "stats": stats,
        "distribution": distribution,
        "recent_alerts": recent_alerts,
        "class_reports": class_reports,
        "terms": terms,
    }
    
    return render(request, "portals/admin/analytics/dashboard.html", context)


@admin_portal_required
def student_risk_radar(request):
    """Early-warning list combining attendance, fees, assessments, discipline and coursework."""
    scoped = get_user_campus_scope(request.user)
    campus_id = scoped.id if scoped is not None else request.GET.get("campus") or None
    rows = build_student_risk_radar(limit=100, campus_id=campus_id)
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for row in rows:
        if row.level in counts:
            counts[row.level] += 1
    return render(
        request,
        "portals/admin/analytics/student_risk_radar.html",
        {"rows": rows, "counts": counts, "selected_campus_id": campus_id},
    )


@admin_portal_required
def student_performance_list(request):
    """List student performance snapshots with filtering"""
    term_id = request.GET.get("term")
    stream_id = request.GET.get("stream")
    risk_filter = request.GET.get("risk")
    search = request.GET.get("search", "").strip()
    
    if term_id:
        term = get_object_or_404(AcademicTerm, id=term_id)
    else:
        term = AcademicTerm.objects.filter(is_current=True).first()
    
    snapshots = _snapshot_queryset_for(request.user).filter(term=term)
    
    if stream_id:
        snapshots = snapshots.filter(stream_id=stream_id)
    
    if risk_filter == "at_risk":
        snapshots = snapshots.filter(is_at_risk=True)
    elif risk_filter == "critical":
        snapshots = snapshots.filter(risk_level="CRITICAL")
    elif risk_filter == "high":
        snapshots = snapshots.filter(risk_level="HIGH")
    
    if search:
        snapshots = snapshots.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__student_id__icontains=search)
        )
    
    snapshots = snapshots.order_by("-gpa", "-overall_percentage")
    
    per_page = _parse_per_page(request, 25)
    paginator = Paginator(snapshots, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    
    # Get filters
    terms = AcademicTerm.objects.all()[:10]
    streams = _stream_queryset_for(request.user)
    
    context = {
        "page_obj": page_obj,
        "term": term,
        "terms": terms,
        "streams": streams,
        "selected_stream": stream_id,
        "risk_filter": risk_filter,
        "search": search,
    }
    
    return render(request, "portals/admin/analytics/student_performance_list.html", context)


@admin_portal_required
def student_performance_detail(request, student_id):
    """Detailed performance view for a student"""
    student = get_object_or_404(_student_queryset_for(request.user), id=student_id)
    term_id = request.GET.get("term")
    
    if term_id:
        term = get_object_or_404(AcademicTerm, id=term_id)
    else:
        term = AcademicTerm.objects.filter(is_current=True).first()
    
    # Get or generate snapshot
    snapshot = StudentPerformanceSnapshot.objects.filter(
        student=student,
        term=term
    ).first()
    
    if not snapshot:
        snapshot = calculate_student_performance_snapshot(student, term)
    
    # Get subject performances
    subject_performances = SubjectPerformance.objects.filter(
        snapshot=snapshot
    ).select_related("course").order_by("-percentage")
    
    # Get performance trends
    trends = PerformanceTrend.objects.filter(
        student=student,
        term__year=term.year,
        course__isnull=True
    ).order_by("term__order")
    
    # Get active alerts
    alerts = AtRiskAlert.objects.filter(
        student=student,
        status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"]
    ).order_by("-created_at")
    
    # Get historical snapshots
    historical_snapshots = StudentPerformanceSnapshot.objects.filter(
        student=student
    ).exclude(id=snapshot.id).order_by("-term__year__name", "-term__order")[:5]
    
    terms = AcademicTerm.objects.all()[:10]
    
    context = {
        "student": student,
        "snapshot": snapshot,
        "subject_performances": subject_performances,
        "trends": trends,
        "alerts": alerts,
        "historical_snapshots": historical_snapshots,
        "term": term,
        "terms": terms,
    }
    
    return render(request, "portals/admin/analytics/student_performance_detail.html", context)


@admin_portal_required
def class_performance_report_view(request, stream_id):
    """Class/stream performance report"""
    stream = get_object_or_404(_stream_queryset_for(request.user), id=stream_id)
    term_id = request.GET.get("term")
    
    if term_id:
        term = get_object_or_404(AcademicTerm, id=term_id)
    else:
        term = AcademicTerm.objects.filter(is_current=True).first()
    
    # Get or generate report
    report = ClassPerformanceReport.objects.filter(
        stream=stream,
        term=term
    ).first()
    
    if not report:
        report = generate_class_performance_report(stream, term)
    
    # Get student snapshots for detailed view
    snapshots = StudentPerformanceSnapshot.objects.filter(
        stream=stream,
        term=term
    ).select_related("student").order_by("-gpa")
    
    # Top performers
    top_performers = snapshots[:10]
    
    # At-risk students
    at_risk_students = snapshots.filter(is_at_risk=True)
    
    # Subject-wise performance
    subject_performances = SubjectPerformance.objects.filter(
        snapshot__in=snapshots
    ).values("course__name").annotate(
        avg_percentage=Avg("percentage"),
        count=Count("id")
    ).order_by("-avg_percentage")
    
    terms = AcademicTerm.objects.all()[:10]
    
    context = {
        "stream": stream,
        "term": term,
        "report": report,
        "top_performers": top_performers,
        "at_risk_students": at_risk_students,
        "subject_performances": subject_performances,
        "terms": terms,
    }
    
    return render(request, "portals/admin/analytics/class_performance_report.html", context)


@admin_portal_required
def at_risk_alerts_list(request):
    """List and manage at-risk student alerts"""
    status_filter = request.GET.get("status", "OPEN")
    severity_filter = request.GET.get("severity")
    search = request.GET.get("search", "").strip()
    
    alerts = _alert_queryset_for(request.user)
    
    if status_filter and status_filter != "ALL":
        alerts = alerts.filter(status=status_filter)
    
    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)
    
    if search:
        alerts = alerts.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(title__icontains=search)
        )
    
    alerts = alerts.order_by("-created_at")
    
    per_page = _parse_per_page(request, 25)
    paginator = Paginator(alerts, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "severity_filter": severity_filter,
        "search": search,
    }
    
    return render(request, "portals/admin/analytics/at_risk_alerts_list.html", context)


@admin_portal_required
def at_risk_alert_detail(request, alert_id):
    """View and manage individual at-risk alert"""
    alert = get_object_or_404(_alert_queryset_for(request.user), id=alert_id)
    teachers = _teacher_queryset_for(request.user)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "acknowledge":
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_by = request.user.teacher_profile
            alert.acknowledged_at = timezone.now()
            alert.save()
            messages.success(request, "Alert acknowledged successfully.")
        
        elif action == "in_progress":
            alert.status = "IN_PROGRESS"
            alert.save()
            messages.success(request, "Alert marked as in progress.")
        
        elif action == "resolve":
            alert.status = "RESOLVED"
            alert.resolved_at = timezone.now()
            alert.resolution_notes = request.POST.get("resolution_notes", "")
            alert.save()
            messages.success(request, "Alert resolved successfully.")
        
        elif action == "dismiss":
            alert.status = "DISMISSED"
            alert.resolution_notes = request.POST.get("resolution_notes", "")
            alert.save()
            messages.success(request, "Alert dismissed.")
        
        elif action == "assign":
            teacher_id = request.POST.get("teacher_id")
            if teacher_id:
                teacher = get_object_or_404(teachers, id=teacher_id)
                alert.assigned_to = teacher
                alert.save()
                messages.success(request, "Alert assigned successfully.")
        
        return redirect("admin_analytics_alert_detail", alert_id=alert.id)
    
    context = {
        "alert": alert,
        "teachers": teachers,
    }
    
    return render(request, "portals/admin/analytics/at_risk_alert_detail.html", context)


@admin_portal_required
def teacher_performance_metrics_view(request):
    """View teacher performance metrics"""
    term_id = request.GET.get("term")
    course_id = request.GET.get("course")
    
    if term_id:
        term = get_object_or_404(AcademicTerm, id=term_id)
    else:
        term = AcademicTerm.objects.filter(is_current=True).first()
    
    metrics = TeacherPerformanceMetrics.objects.filter(
        term=term
    ).select_related("teacher__user", "course")
    scoped = get_user_campus_scope(request.user)
    if scoped is not None:
        metrics = metrics.filter(teacher__campus=scoped)
    
    if course_id:
        metrics = metrics.filter(course_id=course_id)
    
    metrics = metrics.order_by("-average_student_score")
    
    per_page = _parse_per_page(request, 25)
    paginator = Paginator(metrics, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    
    terms = AcademicTerm.objects.all()[:10]
    courses = Course.objects.filter(is_active=True).order_by("name")
    
    context = {
        "page_obj": page_obj,
        "term": term,
        "terms": terms,
        "courses": courses,
        "selected_course": course_id,
    }
    
    return render(request, "portals/admin/analytics/teacher_performance_metrics.html", context)


@admin_portal_required
def generate_snapshots_bulk(request):
    """Generate performance snapshots for all students in a term"""
    if request.method == "POST":
        term_id = request.POST.get("term_id")
        stream_id = request.POST.get("stream_id")
        
        if not term_id:
            messages.error(request, "Please select a term.")
            return redirect("admin_analytics_dashboard")
        
        term = get_object_or_404(AcademicTerm, id=term_id)
        
        students = _student_queryset_for(request.user)
        
        if stream_id:
            students = students.filter(stream_id=stream_id)
        
        count = 0
        for student in students:
            try:
                calculate_student_performance_snapshot(student, term)
                count += 1
            except Exception as e:
                messages.warning(request, f"Error generating snapshot for {student}: {str(e)}")
        
        messages.success(request, f"Successfully generated {count} performance snapshots for {term}.")
        return redirect("admin_analytics_dashboard")
    
    terms = AcademicTerm.objects.all()[:10]
    streams = _stream_queryset_for(request.user)
    
    context = {
        "terms": terms,
        "streams": streams,
    }
    
    return render(request, "portals/admin/analytics/generate_snapshots.html", context)


@admin_portal_required
def performance_trends_chart_data(request, student_id):
    """API endpoint for performance trends chart data"""
    student = get_object_or_404(_student_queryset_for(request.user), id=student_id)
    
    trends = PerformanceTrend.objects.filter(
        student=student,
        course__isnull=True
    ).order_by("term__year__name", "term__order")[:12]
    
    data = {
        "labels": [str(trend.term) for trend in trends],
        "gpa": [float(trend.gpa) if trend.gpa else None for trend in trends],
        "percentage": [float(trend.percentage) if trend.percentage else None for trend in trends],
        "rank": [trend.rank for trend in trends],
    }
    
    return JsonResponse(data)


@admin_portal_required
def subject_performance_chart_data(request, student_id, term_id):
    """API endpoint for subject performance chart data"""
    student = get_object_or_404(_student_queryset_for(request.user), id=student_id)
    term = get_object_or_404(AcademicTerm, id=term_id)
    
    snapshot = StudentPerformanceSnapshot.objects.filter(
        student=student,
        term=term
    ).first()
    
    if not snapshot:
        return JsonResponse({"error": "No snapshot found"}, status=404)
    
    subject_performances = SubjectPerformance.objects.filter(
        snapshot=snapshot
    ).select_related("course").order_by("course__name")
    
    data = {
        "labels": [sp.course.name for sp in subject_performances],
        "percentages": [float(sp.percentage) if sp.percentage else 0 for sp in subject_performances],
        "grades": [sp.grade for sp in subject_performances],
    }
    
    return JsonResponse(data)


@admin_portal_required
def class_performance_chart_data(request, stream_id, term_id):
    """API endpoint for class performance distribution chart"""
    stream = get_object_or_404(_stream_queryset_for(request.user), id=stream_id)
    term = get_object_or_404(AcademicTerm, id=term_id)
    
    report = _class_report_queryset_for(request.user).filter(
        stream=stream,
        term=term
    ).first()
    
    if not report:
        return JsonResponse({"error": "No report found"}, status=404)
    
    data = {
        "distribution": {
            "Excellent (≥3.5)": report.students_excellent,
            "Good (3.0-3.5)": report.students_good,
            "Average (2.5-3.0)": report.students_average,
            "Below Average (2.0-2.5)": report.students_below_average,
            "Failing (<2.0)": report.students_failing,
        },
        "stats": {
            "average_gpa": float(report.average_gpa) if report.average_gpa else 0,
            "highest_gpa": float(report.highest_gpa) if report.highest_gpa else 0,
            "lowest_gpa": float(report.lowest_gpa) if report.lowest_gpa else 0,
        }
    }
    
    return JsonResponse(data)
