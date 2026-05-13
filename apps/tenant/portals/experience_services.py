"""Shared helpers for portal UX (setup checklist, onboarding)."""

from __future__ import annotations

from typing import Any

from django.urls import NoReverseMatch, reverse

from apps.tenant.academics.models import AcademicTerm, AcademicYear
from apps.tenant.finance.models import OutboundMessageLog
from apps.tenant.finance.services import messaging_readiness_snapshot
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile


def _safe_url(name: str) -> str | None:
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def build_school_setup_checklist() -> list[dict[str, Any]]:
    """Non-destructive checklist with deep links into existing admin settings."""
    org = get_or_create_organization()
    org_name_ok = bool(org and org.name and str(org.name).strip())
    has_logo = bool(org and org.logo)
    campus_count = Campus.objects.filter(organization=org).count() if org else 0
    has_year = AcademicYear.objects.filter(is_current=True).exists()
    has_term = AcademicTerm.objects.filter(is_current=True).exists()
    has_student = StudentProfile.objects.exists()

    snap = messaging_readiness_snapshot(sample_limit=10)
    channel = (snap.get("channel") or "SMS").upper()
    if channel == "WHATSAPP":
        messaging_ready = bool(
            snap.get("handler_resolved")
            and snap.get("whatsapp_token_set")
            and snap.get("whatsapp_phone_number_id_set")
        )
    else:
        messaging_ready = bool(snap.get("handler_resolved"))
    portal_link_ok = bool(snap.get("portal_base_configured"))

    items: list[dict[str, Any]] = [
        {
            "key": "org_profile",
            "title": "School name and colours",
            "description": "Set how your school appears in the portal and on messages.",
            "done": org_name_ok,
            "url": _safe_url("admin_orgsettings_org"),
        },
        {
            "key": "logo",
            "title": "School logo (recommended)",
            "description": "Helps parents recognise official messages and the parent portal.",
            "done": has_logo,
            "url": _safe_url("admin_orgsettings_org"),
        },
        {
            "key": "campus",
            "title": "At least one campus",
            "description": "Campuses organise students, staff, and fees.",
            "done": campus_count > 0,
            "url": _safe_url("admin_orgsettings_campuses"),
        },
        {
            "key": "academic_year",
            "title": "Current academic year",
            "description": "Mark which year is active for timetables, assessments, and fees.",
            "done": has_year,
            "url": _safe_url("admin_academic_year_list"),
        },
        {
            "key": "academic_term",
            "title": "Current term",
            "description": "Mark the active term so reporting dates stay accurate.",
            "done": has_term,
            "url": _safe_url("admin_academic_term_list"),
        },
        {
            "key": "messaging",
            "title": "Fee alert channel configured",
            "description": f"Your channel is {channel}. Ensure SMS or WhatsApp sending is set up.",
            "done": messaging_ready,
            "url": _safe_url("admin_finance_messaging_report"),
        },
        {
            "key": "portal_base",
            "title": "Parent portal link in reminders (recommended)",
            "description": "Adds a secure link to invoices in fee reminder text.",
            "done": portal_link_ok,
            "url": None,
        },
        {
            "key": "first_student",
            "title": "Add your first student",
            "description": "You can start with one learner to validate fees and attendance.",
            "done": has_student,
            "url": _safe_url("admin_students_create"),
        },
    ]
    return items


def school_setup_progress() -> dict[str, Any]:
    items = build_school_setup_checklist()
    done = sum(1 for row in items if row.get("done"))
    return {
        "items": items,
        "done_count": done,
        "total": len(items),
        "all_done": done == len(items),
    }


def messaging_activity_summary(days: int = 30):
    from django.utils import timezone
    from datetime import timedelta

    since = timezone.now() - timedelta(days=days)
    qs = OutboundMessageLog.objects.filter(created_at__gte=since)
    return {
        "since": since,
        "total": qs.count(),
        "sent": qs.filter(status=OutboundMessageLog.SENT).count(),
        "failed": qs.filter(status=OutboundMessageLog.FAILED).count(),
        "dry_run": qs.filter(status=OutboundMessageLog.DRY_RUN).count(),
        "no_phone": qs.filter(status=OutboundMessageLog.NO_PHONE).count(),
    }
