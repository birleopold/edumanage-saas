"""Staff-facing UX hub views (communication center, setup guide, system status)."""

from django.contrib import messages
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.tenant.finance.models import CommunicationTemplate, WebhookRetryQueueItem
from apps.tenant.finance.services import messaging_readiness_snapshot

from .experience_services import build_school_health_score, messaging_activity_summary
from .permissions import admin_portal_required
from .setup_audit import school_setup_audit
from .setup_center import school_setup_progress
from .setup_quickstart import (
    bootstrap_class_groups_from_levels,
    bootstrap_uganda_standard_levels,
    class_group_quickstart_plan,
    sync_existing_education_structure,
    uganda_standard_level_plan,
)


def _present_setup_finding(finding):
    """Resolve a setup-audit action URL without letting a missing route break setup."""
    row = dict(finding)
    url_name = row.pop("action_url_name", "")
    try:
        row["action_url"] = reverse(url_name) if url_name else ""
    except NoReverseMatch:
        row["action_url"] = ""
    return row


def _apply_school_setup_audit(progress, audit):
    """Make the existing setup progress reflect verified validity, not counts alone."""
    all_rows = [*progress.get("steps", []), *progress.get("operations", [])]
    by_key = {row["key"]: row for row in all_rows}
    validation_steps = {}

    for key, result in audit["steps"].items():
        blockers = [_present_setup_finding(item) for item in result["blockers"]]
        warnings = [_present_setup_finding(item) for item in result["warnings"]]
        validation_steps[key] = {
            "valid": result["valid"],
            "blockers": blockers,
            "warnings": warnings,
            "metrics": result.get("metrics", {}),
        }

        row = by_key.get(key)
        if row is None:
            continue
        row["blockers"] = blockers
        row["warnings"] = warnings
        row["audit_metrics"] = result.get("metrics", {})

        if blockers:
            row["done"] = False
            row["status"] = "attention" if row.get("optional") else "incomplete"
        elif row.get("done"):
            row["status"] = "complete"
        elif row.get("optional"):
            row["status"] = "optional"

        if blockers:
            row["evidence"] = [
                *row.get("evidence", []),
                f"{len(blockers)} issue{'s' if len(blockers) != 1 else ''} must be fixed before this step is ready",
            ]
        if warnings:
            row["evidence"] = [
                *row.get("evidence", []),
                f"{len(warnings)} review item{'s' if len(warnings) != 1 else ''} — not all warnings block setup",
            ]

    education_row = by_key.get("education_structure")
    if education_row:
        metrics = validation_steps.get("education_structure", {}).get("metrics", {})
        if len(education_row.get("evidence", [])) >= 3:
            education_row["evidence"][2] = (
                f"{metrics.get('mapped_active_level_count', 0)}/{metrics.get('active_level_count', 0)} active levels mapped"
                if metrics.get("active_level_count")
                else "No active levels created yet"
            )

    subject_row = by_key.get("subjects")
    if subject_row:
        metrics = validation_steps.get("subjects", {}).get("metrics", {})
        if len(subject_row.get("evidence", [])) >= 2:
            subject_row["evidence"][1] = (
                f"{metrics.get('current_offering_count', 0)} offering"
                f"{'s' if metrics.get('current_offering_count', 0) != 1 else ''} in the verified current period"
            )

    teaching_row = by_key.get("teaching")
    if teaching_row:
        metrics = validation_steps.get("teaching", {}).get("metrics", {})
        if len(teaching_row.get("evidence", [])) >= 2:
            current_count = metrics.get("current_offering_count", 0)
            assigned_count = metrics.get("assigned_offering_count", 0)
            teaching_row["evidence"][1] = (
                f"{assigned_count}/{current_count} current-period offerings have active teachers"
                if current_count
                else "Create current-period subject offerings first"
            )

    learner_row = by_key.get("learners")
    if learner_row:
        metrics = validation_steps.get("learners", {}).get("metrics", {})
        student_count = metrics.get("active_student_count", 0)
        placed_count = metrics.get("placed_student_count", 0)
        learner_row["evidence"] = [
            *learner_row.get("evidence", []),
            f"{placed_count}/{student_count} active learners have a verified academic placement",
        ]

    required_steps = [row for row in progress.get("steps", []) if not row.get("optional")]
    completed = sum(1 for row in required_steps if row.get("done"))
    total = len(required_steps)
    progress["done_count"] = completed
    progress["remaining_count"] = total - completed
    progress["total"] = total
    progress["percent"] = round((completed / total) * 100) if total else 100
    progress["all_done"] = completed == total
    progress["next_step"] = next((row for row in required_steps if not row.get("done")), None)
    progress["school_setup_validation"] = {
        "steps": validation_steps,
        "blocker_count": audit["blocker_count"],
        "warning_count": audit["warning_count"],
        "core_blocker_count": audit["core_blocker_count"],
    }
    return progress


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
    audit = school_setup_audit(progress["organization"], profile)
    _apply_school_setup_audit(progress, audit)

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
