"""Per-user notification state and safe navigation helpers.

Current notification composition creates one row per recipient. Older records and
integrations can still create audience-level rows with ``recipient=None``. Those
rows must not share one global ``is_read`` flag across every user.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import BooleanField, Case, Exists, F, OuterRef, QuerySet, When
from django.utils import timezone

from .models import ActionLog, Notification


READ_ACTION = "NOTIFICATION_READ"


def is_safe_notification_link(link: object) -> bool:
    """Allow only a same-site absolute path, never a protocol-relative URL."""

    candidate = str(link or "").strip()
    if not candidate:
        return True
    if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return False
    if any(ord(character) < 32 for character in candidate):
        return False

    parsed = urlsplit(candidate)
    return not parsed.scheme and not parsed.netloc


def safe_notification_target(link: object, fallback="notifications_list"):
    candidate = str(link or "").strip()
    return candidate if candidate and is_safe_notification_link(candidate) else fallback


def _notification_content_type():
    return ContentType.objects.get_for_model(Notification, for_concrete_model=True)


def with_user_read_state(queryset: QuerySet, user) -> QuerySet:
    """Annotate visible notifications with the current user's read state."""

    content_type = _notification_content_type()
    receipt = ActionLog.objects.filter(
        content_type=content_type,
        object_id=OuterRef("pk"),
        action=READ_ACTION,
        performed_by=user,
    )
    return queryset.annotate(
        user_is_read=Case(
            When(recipient__isnull=True, then=Exists(receipt)),
            default=F("is_read"),
            output_field=BooleanField(),
        )
    )


def mark_notification_read(notification: Notification, user) -> bool:
    """Mark one visible notification read without changing other users' state."""

    if notification.recipient_id is not None:
        if notification.recipient_id != user.pk:
            return False
        if notification.is_read:
            return False
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        return True

    _, created = ActionLog.objects.get_or_create(
        content_type=_notification_content_type(),
        object_id=notification.pk,
        action=READ_ACTION,
        performed_by=user,
        defaults={
            "content_object": notification,
            "description": "Audience notification marked as read.",
            "metadata": {"notification_id": notification.pk},
        },
    )
    return created


def mark_all_notifications_read(queryset: QuerySet, user) -> int:
    """Mark all currently visible unread notifications read for one user."""

    now = timezone.now()
    queryset = with_user_read_state(queryset, user)
    direct_ids = list(
        queryset.filter(recipient=user, user_is_read=False).values_list("pk", flat=True)
    )
    shared_ids = list(
        queryset.filter(recipient__isnull=True, user_is_read=False).values_list("pk", flat=True)
    )

    content_type = _notification_content_type()
    with transaction.atomic():
        direct_count = Notification.objects.filter(
            pk__in=direct_ids,
            recipient=user,
            is_read=False,
        ).update(is_read=True, read_at=now)

        existing_shared_ids = set(
            ActionLog.objects.filter(
                content_type=content_type,
                object_id__in=shared_ids,
                action=READ_ACTION,
                performed_by=user,
            ).values_list("object_id", flat=True)
        )
        missing_shared_ids = [pk for pk in shared_ids if pk not in existing_shared_ids]
        ActionLog.objects.bulk_create(
            [
                ActionLog(
                    content_type=content_type,
                    object_id=notification_id,
                    action=READ_ACTION,
                    description="Audience notification marked as read.",
                    performed_by=user,
                    metadata={"notification_id": notification_id},
                )
                for notification_id in missing_shared_ids
            ]
        )

    return direct_count + len(missing_shared_ids)
