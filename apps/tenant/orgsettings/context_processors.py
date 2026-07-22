from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.tenant.portals.campus_permissions import get_accessible_campuses
from apps.tenant.users.models import Role

from .models import Notification
from .notification_state import with_user_read_state
from .services import get_current_campus, get_feature_flags, get_or_create_organization


def _notification_preview(item):
    return {
        "title": item.title,
        "message": item.message,
        "priority": item.priority,
        "is_read": getattr(item, "user_is_read", item.is_read),
        "created_at": item.created_at,
        "link": reverse("notifications_read", args=[item.pk]),
    }


def _notification_audiences_for(user):
    audiences = [Notification.ALL]
    if user.has_role(Role.ADMIN):
        audiences.append(Notification.ADMIN)
    if user.has_role(Role.CAMPUS_ADMIN):
        audiences.append(Notification.CAMPUS_ADMIN)
    if user.has_role(Role.TEACHER):
        audiences.append(Notification.TEACHERS)
    if user.has_role(Role.STUDENT):
        audiences.append(Notification.STUDENTS)
    if user.has_role(Role.PARENT):
        audiences.append(Notification.PARENTS)
    if any(
        user.has_role(role)
        for role in (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL, Role.TEACHER)
    ):
        audiences.append(Notification.STAFF)
    return audiences


def orgsettings(request):
    if getattr(connection, "schema_name", None) == "public":
        return {}

    org = get_or_create_organization()
    campus = get_current_campus(request)

    campuses = []
    if org:
        user = getattr(request, "user", None)
        if (
            user
            and user.is_authenticated
            and user.has_role(Role.CAMPUS_ADMIN)
            and not user.has_role(Role.ADMIN)
        ):
            campuses = list(
                get_accessible_campuses(user).filter(is_active=True).order_by("name")
            )
        else:
            campuses = list(org.campuses.filter(is_active=True).order_by("name"))

    # Add cache-busting timestamp for static assets.
    cache_buster = int(timezone.now().timestamp())

    notification_items = []
    unread_notifications_count = 0
    if getattr(request, "user", None) and request.user.is_authenticated:
        role_audiences = _notification_audiences_for(request.user)
        base_notifications = Notification.objects.filter(
            Q(recipient=request.user)
            | Q(recipient__isnull=True, audience__in=role_audiences)
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

        if campus:
            base_notifications = base_notifications.filter(
                Q(campus__isnull=True) | Q(campus=campus)
            )
        else:
            base_notifications = base_notifications.filter(campus__isnull=True)

        base_notifications = with_user_read_state(base_notifications, request.user)
        unread_notifications_count = base_notifications.filter(user_is_read=False).count()
        notification_items = [
            _notification_preview(item)
            for item in base_notifications.select_related("campus")[:8]
        ]

    is_global_admin = bool(
        getattr(request, "user", None)
        and request.user.is_authenticated
        and request.user.has_role(Role.ADMIN)
    )

    schema_name = getattr(connection, "schema_name", "") or ""
    support_email = (getattr(settings, "SUPPORT_CONTACT_EMAIL", "") or "").strip()

    return {
        "org_profile": org,
        "current_campus": campus,
        "campuses": campuses,
        "feature_flags": get_feature_flags(org, campus),
        "cache_buster": cache_buster,
        "notification_items": notification_items,
        "unread_notifications_count": unread_notifications_count,
        "is_global_admin": is_global_admin,
        "portal_support_reference": schema_name if schema_name != "public" else "",
        "support_contact_email": support_email,
    }
