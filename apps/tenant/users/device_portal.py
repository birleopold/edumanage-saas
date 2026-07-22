from importlib.util import find_spec

from decouple import config
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.portals.models import WebPushSubscription
from apps.tenant.portals.permissions import role_required
from apps.tenant.portals.role_navigation import portal_base_template_for
from apps.tenant.portals.push_delivery import send_web_push_to_user

from .models import Role


def base_template_for(user):
    """Compatibility wrapper around the shared portal-shell resolver."""

    return portal_base_template_for(user)


def alert_ready(queryset):
    return queryset.filter(is_active=True).exclude(p256dh_key="").exclude(auth_key="")


def device_counts(queryset):
    """Return all device-state counts in one database aggregate."""

    return queryset.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(is_active=True)),
        ready_count=Count(
            "id",
            filter=Q(is_active=True) & ~Q(p256dh_key="") & ~Q(auth_key=""),
        ),
        error_count=Count("id", filter=~Q(last_error="")),
    )


def pwa_readiness(all_devices):
    public_key = config("WEB_PUSH_PUBLIC_KEY", default="")
    private_key = config("WEB_PUSH_PRIVATE_KEY", default="")
    subject = config("WEB_PUSH_SUBJECT", default="")
    counts = device_counts(all_devices)
    pywebpush_installed = find_spec("pywebpush") is not None
    return {
        "service_worker": True,
        "storage": True,
        "public_key": bool(public_key),
        "private_key": bool(private_key),
        "subject": bool(subject),
        "pywebpush": pywebpush_installed,
        **counts,
        "deliverable": bool(
            public_key
            and private_key
            and pywebpush_installed
            and counts["active_count"]
            and counts["ready_count"]
        ),
    }


@login_required
def my_devices(request):
    devices = WebPushSubscription.objects.filter(user=request.user).order_by(
        "-is_active",
        "-last_seen_at",
        "-updated_at",
    )
    counts = device_counts(devices)
    return render(
        request,
        "auth/devices.html",
        {
            "base_template": base_template_for(request.user),
            "devices": devices,
            "active_count": counts["active_count"],
            "ready_count": counts["ready_count"],
        },
    )


@login_required
@require_POST
def deactivate_my_device(request, pk: int):
    device = get_object_or_404(WebPushSubscription, pk=pk, user=request.user)
    device.is_active = False
    device.last_seen_at = timezone.now()
    device.save(update_fields=["is_active", "last_seen_at", "updated_at"])
    messages.success(request, "PWA alerts disabled for that browser.")
    return redirect("my_devices")


@role_required(Role.ADMIN)
def admin_device_monitor(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    queryset = WebPushSubscription.objects.select_related("user").order_by(
        "-is_active",
        "-last_seen_at",
        "-updated_at",
    )
    if q:
        queryset = queryset.filter(
            Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
            | Q(endpoint__icontains=q)
            | Q(user_agent__icontains=q)
        )
    if status == "active":
        queryset = queryset.filter(is_active=True)
    elif status == "inactive":
        queryset = queryset.filter(is_active=False)
    elif status == "ready":
        queryset = alert_ready(queryset)
    elif status == "missing_keys":
        queryset = queryset.filter(Q(p256dh_key="") | Q(auth_key=""))
    elif status == "error":
        queryset = queryset.exclude(last_error="")

    all_devices = WebPushSubscription.objects.all()
    readiness = pwa_readiness(all_devices)
    page_obj = Paginator(queryset, 30).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/users/device_monitor.html",
        {
            "devices": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "status": status,
            "total_devices": readiness["total_count"],
            "active_devices": readiness["active_count"],
            "ready_devices": readiness["ready_count"],
            "error_devices": readiness["error_count"],
            "readiness": readiness,
        },
    )


@role_required(Role.ADMIN)
@require_POST
def admin_test_pwa_push(request):
    result = send_web_push_to_user(
        request.user,
        title="EduManage test alert",
        body="PWA alerts are working for your account.",
        url="/admin/users/devices/",
    )
    if result["attempted"] == 0:
        messages.warning(
            request,
            "Enable PWA alerts for your account before sending a test alert.",
        )
    elif result["sent"]:
        messages.success(
            request,
            f"Sent {result['sent']} test alert{'' if result['sent'] == 1 else 's'} to your browser.",
        )
    else:
        reasons = sorted(
            {
                item.get("reason", "Unknown delivery error.")
                for item in result["results"]
            }
        )
        messages.error(
            request,
            "Could not send the test alert: " + "; ".join(reasons),
        )
    return redirect("admin_user_devices")
