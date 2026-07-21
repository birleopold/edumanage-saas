from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.orgsettings.models import Campus, Notification
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .notification_forms import NotificationComposerForm
from .notification_state import (
    mark_all_notifications_read,
    mark_notification_read,
    safe_notification_target,
    with_user_read_state,
)
from .services import get_current_campus


AUDIENCE_ROLE_MAP = {
    Notification.ADMIN: [Role.ADMIN],
    Notification.CAMPUS_ADMIN: [Role.CAMPUS_ADMIN],
    Notification.TEACHERS: [Role.TEACHER],
    Notification.STUDENTS: [Role.STUDENT],
    Notification.PARENTS: [Role.PARENT],
    Notification.STAFF: [
        Role.ADMIN,
        Role.CAMPUS_ADMIN,
        Role.PRINCIPAL,
        Role.TEACHER,
    ],
}


def _role_audiences(user):
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


def _notifications_for_user(request):
    user = request.user
    role_audiences = _role_audiences(user)
    current_campus = get_current_campus(request)

    queryset = Notification.objects.filter(
        Q(recipient=user)
        | Q(recipient__isnull=True, audience__in=role_audiences)
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

    if current_campus:
        queryset = queryset.filter(
            Q(campus__isnull=True) | Q(campus=current_campus)
        )
    else:
        queryset = queryset.filter(campus__isnull=True)

    return with_user_read_state(
        queryset.select_related("campus", "created_by"),
        user,
    )


def _users_for_campus(queryset, campus):
    """Resolve campus membership from each role's authoritative school record."""

    return queryset.filter(
        Q(userrole__campus=campus)
        | Q(student_profile__campus=campus)
        | Q(teacher_profile__campus=campus)
        | Q(parent_profile__parentstudentlink__student__campus=campus)
    ).distinct()


def _target_users(form):
    User = get_user_model()
    recipient = form.cleaned_data.get("recipient")
    if recipient:
        return User.objects.filter(pk=recipient.pk, is_active=True)

    audience = form.cleaned_data["audience"]
    campus = form.cleaned_data.get("campus")
    queryset = User.objects.filter(is_active=True)
    role_codes = AUDIENCE_ROLE_MAP.get(audience)
    if role_codes:
        queryset = queryset.filter(roles__code__in=role_codes)
    if campus:
        queryset = _users_for_campus(queryset, campus)
    return queryset.distinct().order_by("id")


@login_required
def notification_list(request):
    q = (request.GET.get("q") or "").strip()
    state = (request.GET.get("state") or "all").strip()
    queryset = _notifications_for_user(request)

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) | Q(message__icontains=q)
        )
    if state == "unread":
        queryset = queryset.filter(user_is_read=False)
    elif state == "read":
        queryset = queryset.filter(user_is_read=True)

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/notifications/list.html",
        {
            "base_template": base_template_for(request.user),
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "state": state,
        },
    )


@login_required
def notification_read(request, pk):
    notification = get_object_or_404(_notifications_for_user(request), pk=pk)
    mark_notification_read(notification, request.user)
    return redirect(safe_notification_target(notification.link))


@login_required
@require_POST
def notification_mark_all_read(request):
    updated = mark_all_notifications_read(
        _notifications_for_user(request),
        request.user,
    )
    if updated:
        messages.success(
            request,
            f"Marked {updated} notification{'s' if updated != 1 else ''} as read.",
        )
    else:
        messages.info(request, "You have no unread notifications.")
    return redirect("notifications_list")


@admin_portal_required
def notification_compose(request):
    scoped_campus = get_user_campus_scope(request.user)
    campus_queryset = Campus.objects.filter(is_active=True).order_by("name")
    user_queryset = (
        get_user_model()
        .objects.filter(is_active=True)
        .order_by("first_name", "last_name", "username")
    )
    if scoped_campus is not None:
        campus_queryset = campus_queryset.filter(pk=scoped_campus.pk)
        user_queryset = _users_for_campus(user_queryset, scoped_campus).order_by(
            "first_name",
            "last_name",
            "username",
        )

    if request.method == "POST":
        form = NotificationComposerForm(
            request.POST,
            campus_queryset=campus_queryset,
            user_queryset=user_queryset,
        )
        if form.is_valid():
            users = list(_target_users(form))
            if scoped_campus is not None:
                allowed_user_ids = set(
                    user_queryset.filter(pk__in=[user.pk for user in users]).values_list(
                        "pk",
                        flat=True,
                    )
                )
                users = [user for user in users if user.pk in allowed_user_ids]

            if not users:
                messages.warning(
                    request,
                    "No active users matched this notification target.",
                )
            else:
                notifications = [
                    Notification(
                        recipient=user,
                        audience=form.cleaned_data["audience"],
                        campus=form.cleaned_data.get("campus"),
                        title=form.cleaned_data["title"],
                        message=form.cleaned_data["message"],
                        priority=form.cleaned_data["priority"],
                        link=form.cleaned_data.get("link", ""),
                        expires_at=form.cleaned_data.get("expires_at"),
                        created_by=request.user,
                    )
                    for user in users
                ]
                Notification.objects.bulk_create(notifications)
                messages.success(
                    request,
                    f"Notification sent to {len(notifications)} user{'s' if len(notifications) != 1 else ''}.",
                )
                return redirect("notifications_list")
    else:
        form = NotificationComposerForm(
            campus_queryset=campus_queryset,
            user_queryset=user_queryset,
        )

    return render(
        request,
        "portals/notifications/composer.html",
        {"base_template": "portals/admin/base.html", "form": form},
    )
