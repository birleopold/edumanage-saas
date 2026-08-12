"""Staff-facing UX hub views (communication center, setup guide, system status)."""

from django.contrib import messages
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenant.finance.models import CommunicationTemplate, WebhookRetryQueueItem
from apps.tenant.finance.services import messaging_readiness_snapshot

from .experience_services import build_school_health_score, messaging_activity_summary
from .permissions import admin_portal_required
from .setup_center import school_setup_progress
from .setup_quickstart import (
    bootstrap_class_groups_from_levels,
    bootstrap_uganda_standard_levels,
    class_group_quickstart_plan,
    sync_existing_education_structure,
    uganda_standard_level_plan,
)


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
    """One guided doorway for initial school and academic configuration."""
    progress = school_setup_progress()
    profile = progress["education_profile"]

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "sync_education_structure":
            summary = sync_existing_education_structure(profile)
            mapping = summary["mapping"]
            links = summary["framework_links"]
            messages.success(
                request,
                "Education structure synchronized: "
                f"{mapping['created']} level mapping(s) created, "
                f"{mapping['updated']} updated, "
                f"{summary['campus_stages_created']} campus stage(s) added and "
                f"{links['updated']} curriculum link(s) refreshed. "
                f"{mapping['manual_preserved']} administrator correction(s) were preserved.",
            )
        elif action == "bootstrap_uganda_levels":
            try:
                summary = bootstrap_uganda_standard_levels(profile)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                sync_summary = summary["sync"]
                messages.success(
                    request,
                    "Uganda level quick start completed: "
                    f"{summary['created_levels']} missing level(s) created, "
                    f"{summary['existing_levels']} existing level(s) preserved and "
                    f"{summary['inactive_preserved']} inactive record(s) left unchanged. "
                    f"{sync_summary['campus_stages_created']} campus stage(s) were added during synchronization.",
                )
        elif action == "bootstrap_class_groups":
            try:
                summary = bootstrap_class_groups_from_levels(profile)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Class-group quick start completed for "
                    f"{summary['campus_name']}: {summary['created_count']} class group(s) created. "
                    f"{len(summary['inactive_preserved'])} inactive existing class group(s) and "
                    f"{len(summary['conflicts_preserved'])} name conflict(s) were left unchanged for administrator review.",
                )
        else:
            messages.warning(request, "No School Setup action was selected.")

        return redirect("admin_school_setup_guide")

    # This page exposes authenticated POST quick actions through progressive
    # enhancement. Force CSRF token creation so the injected forms remain
    # protected by Django's normal CSRF middleware.
    get_token(request)
    uganda_level_plan = uganda_standard_level_plan(profile)
    class_group_plan = class_group_quickstart_plan(profile)
    progress["school_setup_quickstart"] = {
        "uganda_levels_available": bool(uganda_level_plan),
        "uganda_level_names": [row["name"] for row in uganda_level_plan],
        "uganda_stage_selection_required": bool(
            progress.get("is_uganda_framework")
            and not uganda_level_plan
            and profile.institution_type in {"SECONDARY", "MIXED"}
        ),
        "class_groups_available": bool(class_group_plan.get("available")),
        "class_group_level_names": [
            row["level_name"] for row in class_group_plan.get("creatable", [])
        ],
        "class_group_campus_name": class_group_plan.get("campus_name", ""),
        "class_group_reason": class_group_plan.get("reason", ""),
        "class_group_message": class_group_plan.get("message", ""),
    }
    return render(
        request,
        "portals/admin/experience/school_setup_guide.html",
        progress,
    )


@admin_portal_required
def admin_school_health_score(request):
    health = build_school_health_score()
    return render(
        request,
        "portals/admin/experience/school_health_score.html",
        {"health": health},
    )


@admin_portal_required
def admin_school_health_score_data(request):
    health = build_school_health_score()
    return JsonResponse(health)


@admin_portal_required
def admin_system_status(request):
    snap = messaging_readiness_snapshot(sample_limit=20)
    activity = messaging_activity_summary(days=7)
    health = build_school_health_score()
    return render(
        request,
        "portals/admin/experience/system_status.html",
        {
            "messaging": snap,
            "activity": activity,
            "health": health,
        },
    )
