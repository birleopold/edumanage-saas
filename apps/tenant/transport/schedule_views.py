from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import admin_portal_required

from .forms import ParentNotificationForm, RouteScheduleForm
from .models import ParentNotification, RouteSchedule, StudentTransportAssignment, TransportRoute


NOTICE_TEMPLATES = {
    "departed": (ParentNotification.PICKUP, "Bus departed for the scheduled route."),
    "arrived": (ParentNotification.DROPOFF, "Bus arrived at the scheduled stop."),
    "delay": (ParentNotification.DELAY, "Transport is delayed. We shall update you shortly."),
    "route_change": (ParentNotification.GENERAL, "Transport route has changed. Please check the latest route details."),
}


@admin_portal_required
def schedule_list(request):
    schedules = RouteSchedule.objects.select_related("route", "route__vehicle", "route__driver").order_by("route__code", "day_of_week", "start_time")
    return render(request, "portals/admin/transport/schedules_list.html", {"schedules": schedules})


@admin_portal_required
def schedule_create(request):
    route_id = request.GET.get("route")
    initial = {"route": route_id} if route_id else None
    form = RouteScheduleForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        schedule = form.save()
        messages.success(request, "Route schedule saved.")
        return redirect("admin_transport_route_detail", pk=schedule.route_id)
    return render(request, "portals/admin/transport/schedule_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def schedule_edit(request, pk):
    schedule = get_object_or_404(RouteSchedule, pk=pk)
    form = RouteScheduleForm(request.POST or None, instance=schedule)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Route schedule updated.")
        return redirect("admin_transport_route_detail", pk=schedule.route_id)
    return render(request, "portals/admin/transport/schedule_form.html", {"form": form, "schedule": schedule, "mode": "edit"})


@admin_portal_required
def notice_list(request):
    notices = ParentNotification.objects.select_related("assignment", "assignment__student", "assignment__route").order_by("-sent_at")[:200]
    return render(request, "portals/admin/transport/notices_list.html", {"notices": notices})


@admin_portal_required
def notice_create(request):
    template_key = request.GET.get("template") or ""
    initial = {}
    if template_key in NOTICE_TEMPLATES:
        notification_type, message = NOTICE_TEMPLATES[template_key]
        initial = {"notification_type": notification_type, "message": message}
    form = ParentNotificationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Transport notice saved.")
        return redirect("admin_transport_notices_list")
    assignments = StudentTransportAssignment.objects.select_related("student", "route", "stop").filter(is_active=True).order_by("student__last_name")[:100]
    return render(request, "portals/admin/transport/notice_form.html", {"form": form, "assignments": assignments, "templates": NOTICE_TEMPLATES})
