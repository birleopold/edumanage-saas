from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import admin_portal_required

from .forms import RouteScheduleForm
from .models import RouteSchedule, TransportRoute


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    try:
        per_page = int(per_page_raw) if per_page_raw else default
    except (TypeError, ValueError):
        per_page = default
    return max(1, min(per_page, max_value))


@admin_portal_required
def schedule_list(request):
    q = (request.GET.get("q") or "").strip()
    route_filter = (request.GET.get("route") or "").strip()
    day_filter = (request.GET.get("day") or "").strip()
    active_filter = request.GET.get("active", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = RouteSchedule.objects.select_related("route", "route__vehicle", "route__driver").all()
    if q:
        qs = qs.filter(Q(route__name__icontains=q) | Q(route__code__icontains=q) | Q(notes__icontains=q))
    if route_filter:
        try:
            qs = qs.filter(route_id=int(route_filter))
        except (TypeError, ValueError):
            pass
    if day_filter:
        qs = qs.filter(day_of_week=day_filter)
    if active_filter == "1":
        qs = qs.filter(is_active=True)
    elif active_filter == "0":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "portals/admin/transport/schedules_list.html",
        {
            "schedules": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "route_filter": route_filter,
            "day_filter": day_filter,
            "active_filter": active_filter,
            "per_page": per_page,
            "routes_for_filter": TransportRoute.objects.order_by("code", "name"),
            "day_choices": RouteSchedule.DAY_CHOICES,
        },
    )


@admin_portal_required
def schedule_create(request):
    route_id = request.GET.get("route")
    if request.method == "POST":
        form = RouteScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, "Transport schedule created successfully.")
            if route_id:
                return redirect("admin_transport_route_detail", pk=route_id)
            return redirect("admin_transport_schedules_list")
    else:
        initial = {}
        if route_id:
            initial["route"] = route_id
        form = RouteScheduleForm(initial=initial)
    return render(request, "portals/admin/transport/schedule_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def schedule_edit(request, pk: int):
    schedule = get_object_or_404(RouteSchedule.objects.select_related("route"), pk=pk)
    if request.method == "POST":
        form = RouteScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "Transport schedule updated successfully.")
            return redirect("admin_transport_schedules_list")
    else:
        form = RouteScheduleForm(instance=schedule)
    return render(request, "portals/admin/transport/schedule_form.html", {"form": form, "mode": "edit", "schedule": schedule})
