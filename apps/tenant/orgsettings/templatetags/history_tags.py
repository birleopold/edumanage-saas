from django import template
from django.contrib.contenttypes.models import ContentType

from apps.tenant.orgsettings.models import ActionLog, StatusHistory


register = template.Library()


def _actor_name(user):
    if not user:
        return "System"
    return user.get_full_name() or user.get_username()


def _metadata_items(metadata):
    if not isinstance(metadata, dict):
        return []
    return [{"key": key, "value": value} for key, value in metadata.items()]


@register.inclusion_tag("components/history_timeline.html")
def history_timeline(obj, title="History Timeline", limit=30):
    """Render StatusHistory and ActionLog records for any model instance."""
    if not obj or not getattr(obj, "pk", None):
        return {"title": title, "events": []}

    content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
    status_events = StatusHistory.objects.filter(content_type=content_type, object_id=obj.pk).select_related("changed_by")
    action_events = ActionLog.objects.filter(content_type=content_type, object_id=obj.pk).select_related("performed_by")

    events = []
    for item in status_events:
        events.append(
            {
                "kind": "status",
                "label": "Status changed",
                "timestamp": item.created_at,
                "actor": _actor_name(item.changed_by),
                "old_status": item.old_status,
                "new_status": item.new_status,
                "reason": item.reason,
                "metadata": _metadata_items(getattr(item, "metadata", {}) or {}),
            }
        )

    for item in action_events:
        events.append(
            {
                "kind": "action",
                "label": item.action,
                "timestamp": item.created_at,
                "actor": _actor_name(item.performed_by),
                "old_status": "",
                "new_status": "",
                "reason": item.description,
                "metadata": _metadata_items(item.metadata or {}),
            }
        )

    events.sort(key=lambda row: row["timestamp"], reverse=True)
    return {"title": title, "events": events[: int(limit or 30)]}
