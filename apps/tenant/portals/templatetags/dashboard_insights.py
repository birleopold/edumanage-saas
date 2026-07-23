from __future__ import annotations

from datetime import timedelta

from django import template
from django.db.models import Count
from django.utils import timezone

from apps.tenant.audit.models import AuditEvent
from apps.tenant.portals.campus_permissions import get_user_campus_scope


register = template.Library()


_ACTION_PRESENTATION = {
    AuditEvent.CREATE: ("Created", "ph-plus-circle", "create"),
    AuditEvent.EDIT: ("Updated", "ph-pencil-simple", "edit"),
    AuditEvent.DELETE: ("Deleted", "ph-trash", "delete"),
    AuditEvent.EXPORT: ("Exported", "ph-file-arrow-down", "export"),
    AuditEvent.PRINT: ("Printed", "ph-printer", "export"),
    AuditEvent.DOWNLOAD: ("Downloaded", "ph-download-simple", "export"),
    AuditEvent.LOGIN: ("Signed in", "ph-sign-in", "login"),
    AuditEvent.LOGOUT: ("Signed out", "ph-sign-out", "login"),
    AuditEvent.PASSWORD: ("Changed security details", "ph-password", "edit"),
    AuditEvent.VIEW: ("Viewed", "ph-eye", "view"),
}


def _event_title(event: AuditEvent) -> str:
    label, _icon, _tone = _ACTION_PRESENTATION.get(
        event.action,
        (event.get_action_display(), "ph-pulse", "view"),
    )
    target = (event.object_label or event.view_name or event.path or "school record").strip()
    return f"{label} {target}"


def _event_detail(event: AuditEvent) -> str:
    actor = event.user.get_full_name() if event.user_id else "System"
    actor = actor or getattr(event.user, "username", "System")
    campus = f" · {event.campus}" if event.campus_id else ""
    return f"{actor}{campus}"


@register.inclusion_tag("components/admin_dashboard_insights.html", takes_context=True)
def admin_dashboard_insights(context):
    """Render campus-safe activity and seven-day action summaries."""

    request = context.get("request")
    if request is None or not getattr(request, "user", None):
        return {"activity_items": [], "activity_bars": [], "activity_total": 0}

    queryset = AuditEvent.objects.select_related("user", "campus")
    try:
        campus = get_user_campus_scope(request.user)
    except Exception:
        campus = None

    if campus is not None:
        queryset = queryset.filter(campus=campus)

    recent_events = list(queryset.order_by("-created_at")[:6])
    activity_items = []
    for event in recent_events:
        _label, icon, tone = _ACTION_PRESENTATION.get(
            event.action,
            (event.get_action_display(), "ph-pulse", "view"),
        )
        activity_items.append(
            {
                "title": _event_title(event),
                "detail": _event_detail(event),
                "icon": icon,
                "tone": tone,
                "created_at": event.created_at,
            }
        )

    since = timezone.now() - timedelta(days=7)
    grouped = list(
        queryset.filter(created_at__gte=since)
        .values("action")
        .annotate(total=Count("id"))
        .order_by("-total", "action")[:5]
    )
    activity_total = sum(row["total"] for row in grouped)
    maximum = max((row["total"] for row in grouped), default=0)
    activity_bars = []
    for row in grouped:
        label, _icon, _tone = _ACTION_PRESENTATION.get(
            row["action"],
            (str(row["action"]).replace("_", " ").title(), "ph-pulse", "view"),
        )
        activity_bars.append(
            {
                "label": label,
                "count": row["total"],
                "percent": round((row["total"] / maximum) * 100) if maximum else 0,
            }
        )

    return {
        "activity_items": activity_items,
        "activity_bars": activity_bars,
        "activity_total": activity_total,
    }
