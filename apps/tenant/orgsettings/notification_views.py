from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.orgsettings.models import Campus, Notification
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .notification_forms import NotificationComposerForm
from .services import get_current_campus


AUDIENCE_ROLE_MAP = {
    Notification.ADMIN: [Role.ADMIN],
    Notification.CAMPUS_ADMIN: [Role.CAMPUS_ADMIN],
    Notification.TEACHERS: [Role.TEACHER],
    Notification.STUDENTS: [Role.STUDENT],
    Notification.PARENTS: [Role.PARENT],
    Notification.STAFF: [Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL, Role.TEACHER],
}


def _role_audiences(user):
    audiences = [Notification.ALL]
    if user.has_role(Role.ADMIN):
        audiences.append(Notification.ADMIN)
    if user.has_role(Role.CAMPUS_ADMIN):
        audiences.append(Notification.CAMPUS_ADMIN)
    if user.has_role(Role.TEACHER):
        audiences.extend([Notification.TEACHERS, Notification.STAFF])
    if user.has_role(Role.STUDENT):
        audiences.append(Notification.STUDENTS)
    if user.has_role(Role.PARENT):
        audiences.append(Notification.PARENTS)
    return audiences


def _base_template_for(user):
    if user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN):
        return "portals/admin/base.html"
    if user.has_role(Role.TEACHER):
        return "portals/teacher/base.html"
    if user.has_role(Role.STUDENT):
        return "portals/student/base.html"
    if user.has_role(Role.PARENT):
        return "portals/parent/base.html"
    return "portals/admin/base.html"


def _notifications_for_user(request):
    user = request.user
    role_audiences = _role_audiences(user)
    current_campus = get_current_campus(request)

    qs = Notification.objects.filter(
        Q(recipient=user) | Q(recipient__isnull=True, audience__in=role_audiences)
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

    if current_campus:
        qs = qs.filter(Q(campus__isnull=True) | Q(campus=current_campus))
    else:
        qs = qs.filter(campus__isnull=True)

    return qs.select_related("campus", "created_by")


def _target_users(form, created_by):
    User = get_user_model()
    recipient = form.cleaned_data.get("recipient")
    if recipient:
        return User.objects.filter(pk=recipient.pk, is_active=True)

    audience = form.cleaned_data["audience"]
    campus = form.cleaned_data.get("campus")
    qs = User.objects.filter(is_active=True)
    role_codes = AUDIENCE_ROLE_MAP.get(audience)
    if role_codes:
        qs = qs.filter(roles__code__in=role_codes)
    if campus:
        qs = qs.filter(userrole__campus=campus)
    return qs.distinct().order_by("id")


@login_required
def notification_list(request):
    q = (request.GET.get("q") or "").strip()
    state = (request.GET.get("state") or "all").strip()
    qs = _notifications_for_user(request)

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(message__icontains=q))
    if state == "unread":
        qs = qs.filter(is_read=False)
    elif state == "read":
        qs = qs.filter(is_read=True)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/notifications/list.html",
        {
            "base_template": _base_template_for(request.user),
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "state": state,
        },
    )


@login_required
def notification_read(request, pk):
    notification = get_object_or_404(_notifications_for_user(request), pk=pk)
    notification.mark_as_read()
    target = notification.link or "notifications_list"
    return redirect(target)


@login_required
@require_POST
def notification_mark_all_read(request):
    updated = _notifications_for_user(request).filter(is_read=False).update(is_read=True, read_at=timezone.now())
    messages.success(request, f"Marked {updated} notification(s) as read.")
    return redirect("notifications_list")


@admin_portal_required
def notification_compose(request):
    scoped_campus = get_user_campus_scope(request.user)
    campus_qs = Campus.objects.filter(is_active=True).order_by("name")
    user_qs = get_user_model().objects.filter(is_active=True).order_by("first_name", "last_name", "username")
    if scoped_campus is not None:
        campus_qs = campus_qs.filter(pk=scoped_campus.pk)
        user_qs = user_qs.filter(userrole__campus=scoped_campus).distinct()

    if request.method == "POST":
        form = NotificationComposerForm(request.POST, campus_queryset=campus_qs, user_queryset=user_qs)
        if form.is_valid():
            users = list(_target_users(form, request.user))
            if scoped_campus is not None:
                users = [user for user in users if user_qs.filter(pk=user.pk).exists()]
            if not users:
                messages.warning(request, "No active users matched this notification target.")
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
                messages.success(request, f"Notification sent to {len(notifications)} user(s).")
                return redirect("notifications_list")
    else:
        form = NotificationComposerForm(campus_queryset=campus_qs, user_queryset=user_qs)

    return render(
        request,
        "portals/notifications/composer.html",
        {"base_template": "portals/admin/base.html", "form": form},
    )
