from django.contrib import messages
from django.shortcuts import redirect, render

from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role, UserRole

from .models import AuditEvent, BackupJob, ConsentRecord, DataRetentionPolicy, ExportPermission, LoginHistory, SuspiciousLoginAlert


@admin_portal_required
def dashboard(request):
    return render(request, "portals/audit/dashboard.html", {"events": AuditEvent.objects.select_related("user")[:50], "logins": LoginHistory.objects.select_related("user")[:30], "alerts": SuspiciousLoginAlert.objects.filter(status=SuspiciousLoginAlert.OPEN)[:30], "exports": ExportPermission.objects.select_related("user")[:50], "consents": ConsentRecord.objects.all()[:30], "backups": BackupJob.objects.all()[:10]})


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
