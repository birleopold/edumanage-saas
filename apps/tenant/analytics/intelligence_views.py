from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, Stream
from apps.tenant.portals.permissions import admin_portal_required, role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .intelligence import attendance_performance_correlation, run_analytics
from .intelligence_models import AnalyticsRun, Intervention, ReportCardCommentSuggestion, StudentRecommendation
from .models import AtRiskAlert, ClassPerformanceReport, PerformanceTrend, StudentPerformanceSnapshot, TeacherPerformanceMetrics


@admin_portal_required
def intelligence_dashboard(request):
    term = AcademicTerm.objects.filter(is_current=True).first() or AcademicTerm.objects.order_by("-year__name", "-order").first()
    if request.method == "POST":
        run = run_analytics(term=term, run_type=AnalyticsRun.MANUAL)
        messages.success(request, f"Analytics generated: {run.generated_snapshots} snapshots, {run.generated_alerts} alerts.")
        return redirect("admin_analytics_intelligence")
    snapshots = StudentPerformanceSnapshot.objects.filter(term=term) if term else StudentPerformanceSnapshot.objects.none()
    context = {
        "term": term,
        "latest_run": AnalyticsRun.objects.first(),
        "runs": AnalyticsRun.objects.all()[:10],
        "at_risk": snapshots.filter(is_at_risk=True)[:20],
        "recommendations": StudentRecommendation.objects.filter(status=StudentRecommendation.OPEN)[:20],
        "correlation": attendance_performance_correlation(term) if term else None,
        "class_reports": ClassPerformanceReport.objects.filter(term=term).select_related("stream") if term else [],
        "teacher_metrics": TeacherPerformanceMetrics.objects.filter(term=term).select_related("teacher", "course")[:20] if term else [],
    }
    return render(request, "portals/admin/analytics/intelligence_dashboard.html", context)


@admin_portal_required
def intervention_create(request, alert_id):
    alert = get_object_or_404(AtRiskAlert.objects.select_related("student"), pk=alert_id)
    if request.method == "POST":
        Intervention.objects.create(alert=alert, student=alert.student, assigned_to=alert.assigned_to, title=request.POST.get("title") or "Learner support intervention", plan=request.POST.get("plan") or alert.recommended_actions, target_date=request.POST.get("target_date") or None, created_by=request.user)
        alert.status = AtRiskAlert.IN_PROGRESS
        alert.save(update_fields=["status"])
        messages.success(request, "Intervention recorded.")
        return redirect("admin_analytics_alert_detail", alert_id=alert.id)
    return render(request, "portals/admin/analytics/intervention_form.html", {"alert": alert})


@admin_portal_required
def intervention_update(request, pk):
    item = get_object_or_404(Intervention, pk=pk)
    if request.method == "POST":
        item.status = request.POST.get("status") or item.status
        item.progress_note = request.POST.get("progress_note") or item.progress_note
        item.outcome = request.POST.get("outcome") or item.outcome
        item.save()
        messages.success(request, "Intervention updated.")
        return redirect("admin_analytics_alert_detail", alert_id=item.alert_id)
    return render(request, "portals/admin/analytics/intervention_form.html", {"intervention": item, "alert": item.alert})


@admin_portal_required
def class_comparison_data(request):
    term_id = request.GET.get("term")
    term = get_object_or_404(AcademicTerm, pk=term_id) if term_id else AcademicTerm.objects.filter(is_current=True).first()
    rows = ClassPerformanceReport.objects.filter(term=term).select_related("stream").order_by("stream__class_group__name", "stream__name")
    return JsonResponse({"labels": [str(r.stream) for r in rows], "average_percentage": [float(r.average_percentage or 0) for r in rows], "at_risk": [r.at_risk_count for r in rows]})


@admin_portal_required
def attendance_correlation_data(request):
    term_id = request.GET.get("term")
    term = get_object_or_404(AcademicTerm, pk=term_id) if term_id else AcademicTerm.objects.filter(is_current=True).first()
    rows = StudentPerformanceSnapshot.objects.filter(term=term, attendance_percentage__isnull=False, overall_percentage__isnull=False).select_related("student")
    return JsonResponse({"points": [{"student": str(r.student), "attendance": float(r.attendance_percentage), "performance": float(r.overall_percentage)} for r in rows], "summary": attendance_performance_correlation(term)})


@role_required(Role.TEACHER)
def teacher_dashboard(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    metrics = TeacherPerformanceMetrics.objects.filter(teacher=teacher).select_related("term", "course") if teacher else []
    alerts = AtRiskAlert.objects.filter(assigned_to=teacher).select_related("student", "snapshot")[:30] if teacher else []
    return render(request, "portals/teacher/analytics/dashboard.html", {"teacher": teacher, "metrics": metrics, "alerts": alerts})


@role_required(Role.STUDENT)
def student_trends(request):
    student = StudentProfile.objects.filter(user=request.user).first()
    trends = PerformanceTrend.objects.filter(student=student, course__isnull=True).select_related("term") if student else []
    comments = ReportCardCommentSuggestion.objects.filter(student=student).select_related("term") if student else []
    return render(request, "portals/student/analytics/trends.html", {"student": student, "trends": trends, "comments": comments})


@role_required(Role.PARENT)
def parent_trends(request):
    from apps.tenant.parents.models import ParentProfile, ParentStudentLink
    parent = ParentProfile.objects.filter(user=request.user).first()
    links = ParentStudentLink.objects.filter(parent=parent).select_related("student") if parent else []
    data = []
    for link in links:
        data.append({"student": link.student, "trends": PerformanceTrend.objects.filter(student=link.student, course__isnull=True).select_related("term"), "comments": ReportCardCommentSuggestion.objects.filter(student=link.student).select_related("term")})
    return render(request, "portals/parent/analytics/trends.html", {"parent": parent, "children_data": data})
