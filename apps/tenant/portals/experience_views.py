"""Staff-facing UX hub views (communication center, setup guide, system status)."""

from django.shortcuts import render
from django.utils import timezone

from apps.tenant.finance.models import CommunicationTemplate, WebhookRetryQueueItem
from apps.tenant.finance.services import messaging_readiness_snapshot

from .experience_services import messaging_activity_summary, school_setup_progress
from .permissions import admin_portal_required


@admin_portal_required
def admin_communication_center(request):
    """Single place for messaging tools, templates, and documentation links."""
    activity = messaging_activity_summary(days=30)
    templates_qs = CommunicationTemplate.objects.filter(is_active=True).order_by(
        "sort_order", "name"
    )
    retry_due = WebhookRetryQueueItem.objects.filter(
        is_active=True,
        next_attempt_at__lte=timezone.now(),
    ).count()
    return render(
        request,
        "portals/admin/experience/communication_center.html",
        {
            "activity": activity,
            "communication_templates": templates_qs,
            "webhook_retry_due_count": retry_due,
        },
    )


@admin_portal_required
def admin_school_setup_guide(request):
    progress = school_setup_progress()
    return render(
        request,
        "portals/admin/experience/school_setup_guide.html",
        progress,
    )


@admin_portal_required
def admin_system_status(request):
    snap = messaging_readiness_snapshot(sample_limit=20)
    activity = messaging_activity_summary(days=7)
    return render(
        request,
        "portals/admin/experience/system_status.html",
        {
            "messaging": snap,
            "activity": activity,
        },
    )
