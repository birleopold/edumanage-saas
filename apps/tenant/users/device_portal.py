from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.portals.permissions import role_required

from .models import MobileDevice, Role


PLATFORM_CHOICES = dict(MobileDevice.PLATFORM_CHOICES)


def base_template_for(user):
    if user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN):
        return "portals/admin/base.html"
    if user.has_role(Role.TEACHER):
        return "portals/teacher/base.html"
    if user.has_role(Role.STUDENT):
        return "portals/student/base.html"
    if user.has_role(Role.PARENT):
        return "portals/parent/base.html"
    return "portals/admin/base.html"


@login_required
def my_devices(request):
    devices = MobileDevice.objects.filter(user=request.user).order_by("-is_active", "-last_seen_at")
    return render(
        request,
        "auth/devices.html",
        {
            "base_template": base_template_for(request.user),
            "devices": devices,
            "active_count": devices.filter(is_active=True).count(),
            "ready_count": devices.filter(is_active=True).exclude(push_token="").count(),
        },
    )


@login_required
@require_POST
def deactivate_my_device(request, pk: int):
    device = get_object_or_404(MobileDevice, pk=pk, user=request.user)
    device.is_active = False
    device.push_token = ""
    device.last_seen_at = timezone.now()
    device.save(update_fields=["is_active", "push_token", "last_seen_at"])
    messages.success(request, "Device deactivated.")
    return redirect("my_devices")


@role_required(Role.ADMIN)
def admin_device_monitor(request):
    q = (request.GET.get("q") or "").strip()
    platform = (request.GET.get("platform") or "").strip().upper()
    status = (request.GET.get("status") or "").strip()

    qs = MobileDevice.objects.select_related("user").order_by("-last_seen_at")
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
            | Q(device_id__icontains=q)
            | Q(app_version__icontains=q)
        )
    if platform in PLATFORM_CHOICES:
        qs = qs.filter(platform=platform)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    elif status == "ready":
        qs = qs.filter(is_active=True).exclude(push_token="")
    elif status == "missing_token":
        qs = qs.filter(Q(push_token="") | Q(push_token__isnull=True))

    page_obj = Paginator(qs, 30).get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/users/device_monitor.html",
        {
            "devices": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "platform": platform,
            "status": status,
            "platform_choices": MobileDevice.PLATFORM_CHOICES,
            "total_devices": MobileDevice.objects.count(),
            "active_devices": MobileDevice.objects.filter(is_active=True).count(),
            "ready_devices": MobileDevice.objects.filter(is_active=True).exclude(push_token="").count(),
        },
    )
