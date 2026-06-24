from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render

from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role, UserRole

from .models import AuditEvent, BackupJob, ConsentRecord, DataRetentionPolicy, ExportPermission, LoginHistory, SuspiciousLoginAlert


TRUST_ACTIVITY_CATEGORIES = {
    "students": {
        "title": "Who added or changed a student?",
        "description": "Tracks student creation, profile edits, imports and student record changes.",
        "icon": "ph-student",
        "query": Q(path__icontains="/students") | Q(object_label__icontains="student") | Q(metadata__icontains="student"),
    },
    "fees": {
        "title": "Who edited fees or payments?",
        "description": "Tracks fee items, invoices, payments, receipts and finance adjustments.",
        "icon": "ph-wallet",
        "query": Q(path__icontains="/finance") | Q(object_label__icontains="fee") | Q(object_label__icontains="invoice") | Q(object_label__icontains="payment") | Q(metadata__icontains="fee"),
    },
    "payroll": {
        "title": "Who approved or changed payroll?",
        "description": "Tracks payroll, payslip and staff payment workflows.",
        "icon": "ph-bank",
        "query": Q(path__icontains="payroll") | Q(path__icontains="payslip") | Q(object_label__icontains="payroll") | Q(metadata__icontains="payroll"),
    },
    "exam_results": {
        "title": "Who changed exam results?",
        "description": "Tracks exams, assessments, marks, scores and published result changes.",
        "icon": "ph-exam",
        "query": Q(path__icontains="/exams") | Q(path__icontains="/assessments") | Q(path__icontains="results") | Q(object_label__icontains="mark") | Q(object_label__icontains="result") | Q(metadata__icontains="result"),
    },
}


def _filtered_activity_queryset(request):
    qs = AuditEvent.objects.select_related("user", "campus").order_by("-created_at")
    category = request.GET.get("category") or ""
    action = request.GET.get("action") or ""
    q = (request.GET.get("q") or "").strip()

    if category in TRUST_ACTIVITY_CATEGORIES:
        qs = qs.filter(TRUST_ACTIVITY_CATEGORIES[category]["query"])
    if action:
        qs = qs.filter(action=action)
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(path__icontains=q)
            | Q(view_name__icontains=q)
            | Q(object_label__icontains=q)
            | Q(metadata__icontains=q)
        )
    return qs


def _trust_question_cards():
    cards = []
    base = AuditEvent.objects.select_related("user", "campus").order_by("-created_at")
    for key, config in TRUST_ACTIVITY_CATEGORIES.items():
        qs = base.filter(config["query"])
        cards.append(
            {
                "key": key,
                "title": config["title"],
                "description": config["description"],
                "icon": config["icon"],
                "count": qs.count(),
                "latest": qs.first(),
            }
        )
    return cards


@admin_portal_required
def dashboard(request):
    trust_cards = _trust_question_cards()
    return render(
        request,
        "portals/audit/dashboard.html",
        {
            "events": AuditEvent.objects.select_related("user", "campus")[:50],
            "logins": LoginHistory.objects.select_related("user")[:30],
            "alerts": SuspiciousLoginAlert.objects.filter(status=SuspiciousLoginAlert.OPEN)[:30],
            "exports": ExportPermission.objects.select_related("user")[:50],
            "consents": ConsentRecord.objects.all()[:30],
            "backups": BackupJob.objects.all()[:10],
            "trust_cards": trust_cards,
            "sensitive_events": _filtered_activity_queryset(request)[:12],
        },
    )


@admin_portal_required
def activity_timeline(request):
    category = request.GET.get("category") or ""
    action = request.GET.get("action") or ""
    q = (request.GET.get("q") or "").strip()
    events = _filtered_activity_queryset(request)[:200]
    return render(
        request,
        "portals/audit/activity_timeline.html",
        {
            "events": events,
            "trust_cards": _trust_question_cards(),
            "categories": TRUST_ACTIVITY_CATEGORIES,
            "active_category": category,
            "active_action": action,
            "q": q,
            "action_choices": AuditEvent.ACTION_CHOICES,
        },
    )


@admin_portal_required
def permission_review(request):
    campus_admin_without_campus = UserRole.objects.filter(role__code=Role.CAMPUS_ADMIN, campus__isnull=True).select_related("user", "role", "campus")
    superusers = UserRole.objects.filter(user__is_superuser=True).select_related("user", "role", "campus")
    return render(request, "portals/audit/permission_review.html", {"campus_admin_without_campus": campus_admin_without_campus, "superusers": superusers})


@admin_portal_required
def retention_rules(request):
    if request.method == "POST":
        module = request.POST.get("module") or "general"
        days = int(request.POST.get("retention_days") or 2555)
        DataRetentionPolicy.objects.update_or_create(module=module, defaults={"retention_days": days, "action_after_retention": request.POST.get("action_after_retention") or "ARCHIVE", "is_active": bool(request.POST.get("is_active")), "notes": request.POST.get("notes") or ""})
        messages.success(request, "Retention rule saved.")
        return redirect("audit_retention_rules")
    return render(request, "portals/audit/retention_rules.html", {"rules": DataRetentionPolicy.objects.all()})


@admin_portal_required
def backup_jobs(request):
    if request.method == "POST":
        BackupJob.objects.create(requested_by=request.user, status=BackupJob.REQUESTED, notes=request.POST.get("notes") or "Manual backup requested")
        messages.success(request, "Backup request recorded.")
        return redirect("audit_backup_jobs")
    return render(request, "portals/audit/backup_jobs.html", {"backups": BackupJob.objects.all()[:50]})
