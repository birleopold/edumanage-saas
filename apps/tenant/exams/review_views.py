import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.portals.permissions import admin_portal_required

from .models import Exam, ExamAntiCheatEvent, ExamPaper, OnlineExamAttempt, StudentResponse


def _filtered_attempts(request):
    qs = OnlineExamAttempt.objects.select_related("student", "paper", "paper__exam", "paper__offering__course").annotate(event_count=Count("security_events"))
    exam_id = request.GET.get("exam") or ""
    paper_id = request.GET.get("paper") or ""
    student = (request.GET.get("student") or "").strip()
    event_type = request.GET.get("event_type") or ""
    ip = (request.GET.get("ip") or "").strip()
    warnings = request.GET.get("warnings") or ""

    if exam_id:
        qs = qs.filter(paper__exam_id=exam_id)
    if paper_id:
        qs = qs.filter(paper_id=paper_id)
    if student:
        qs = qs.filter(Q(student__first_name__icontains=student) | Q(student__last_name__icontains=student) | Q(student__student_id__icontains=student))
    if event_type:
        qs = qs.filter(security_events__event_type=event_type)
    if ip:
        qs = qs.filter(Q(ip_address__icontains=ip) | Q(submitted_by_ip__icontains=ip) | Q(security_events__ip_address__icontains=ip))
    if warnings:
        try:
            qs = qs.filter(browser_focus_warnings__gte=int(warnings))
        except ValueError:
            pass
    return qs.distinct().order_by("-started_at")


@admin_portal_required
def review_dashboard(request):
    attempts = _filtered_attempts(request)
    events = ExamAntiCheatEvent.objects.select_related("attempt", "attempt__student", "attempt__paper", "attempt__paper__exam").order_by("-created_at")
    event_type = request.GET.get("event_type") or ""
    if event_type:
        events = events.filter(event_type=event_type)
    total_events = ExamAntiCheatEvent.objects.count()
    unresolved_events = ExamAntiCheatEvent.objects.exclude(metadata__review_status="resolved").count()
    locked_attempts = OnlineExamAttempt.objects.filter(locked_at__isnull=False).count()
    high_warning_attempts = OnlineExamAttempt.objects.filter(browser_focus_warnings__gte=3).count()
    paginator = Paginator(attempts, 30)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/exams/review_dashboard.html",
        {
            "page_obj": page_obj,
            "attempts": page_obj.object_list,
            "events": events[:30],
            "exams": Exam.objects.order_by("-created_at")[:100],
            "papers": ExamPaper.objects.select_related("exam", "offering__course").order_by("-created_at")[:200],
            "event_choices": ExamAntiCheatEvent.EVENT_CHOICES,
            "total_events": total_events,
            "unresolved_events": unresolved_events,
            "locked_attempts": locked_attempts,
            "high_warning_attempts": high_warning_attempts,
            "filters": request.GET,
        },
    )


@admin_portal_required
def attempt_review(request, pk):
    attempt = get_object_or_404(
        OnlineExamAttempt.objects.select_related("student", "paper", "paper__exam", "paper__offering__course").prefetch_related("security_events", "responses__exam_question__question"),
        pk=pk,
    )
    events = attempt.security_events.all().order_by("created_at")
    responses = attempt.responses.select_related("exam_question", "exam_question__question").order_by("exam_question__order")
    return render(request, "portals/admin/exams/review_attempt.html", {"attempt": attempt, "events": events, "responses": responses})


@admin_portal_required
def event_detail(request, pk):
    event = get_object_or_404(ExamAntiCheatEvent.objects.select_related("attempt", "attempt__student", "attempt__paper", "attempt__paper__exam"), pk=pk)
    return render(request, "portals/admin/exams/review_event.html", {"event": event})


@admin_portal_required
@require_POST
def resolve_event(request, pk):
    event = get_object_or_404(ExamAntiCheatEvent, pk=pk)
    metadata = dict(event.metadata or {})
    metadata["review_status"] = request.POST.get("status") or "resolved"
    metadata["review_note"] = request.POST.get("note") or ""
    metadata["reviewed_by"] = request.user.get_username()
    metadata["reviewed_at"] = timezone.now().isoformat()
    event.metadata = metadata
    event.save(update_fields=["metadata"])
    messages.success(request, "Review status updated.")
    return redirect("admin_exam_review_event", pk=event.pk)


@admin_portal_required
def export_review_csv(request):
    attempts = _filtered_attempts(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="exam_review_follow_up.csv"'
    writer = csv.writer(response)
    writer.writerow(["Attempt ID", "Exam", "Paper", "Student", "Status", "Started", "Submitted", "Start IP", "Submit IP", "Warnings", "Locked Reason", "Event Count"])
    for attempt in attempts:
        writer.writerow([
            attempt.pk,
            attempt.paper.exam.name,
            str(attempt.paper),
            attempt.student.get_full_name(),
            attempt.get_status_display(),
            attempt.started_at,
            attempt.submitted_at,
            attempt.ip_address,
            attempt.submitted_by_ip,
            attempt.browser_focus_warnings,
            attempt.locked_reason,
            attempt.event_count,
        ])
    return response
