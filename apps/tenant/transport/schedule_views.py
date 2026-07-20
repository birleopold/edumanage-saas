from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .forms import ParentNotificationForm, RouteScheduleForm
from .models import ParentNotification, RouteSchedule, StudentTransportAssignment, TransportRoute


NOTICE_TEMPLATES = {
    "departed": (ParentNotification.PICKUP, "The school vehicle has departed for the scheduled route."),
    "arrived": (ParentNotification.DROPOFF, "The school vehicle has arrived at the scheduled stop."),
    "delay": (ParentNotification.DELAY, "Transport is delayed. We will provide another update shortly."),
    "route_change": (
        ParentNotification.GENERAL,
        "The transport route has changed. Please review the latest route details.",
    ),
}


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    try:
        per_page = int(per_page_raw) if per_page_raw else default
    except (TypeError, ValueError):
        per_page = default
    return max(1, min(per_page, max_value))


def _assignment_queryset_for(user):
    queryset = StudentTransportAssignment.objects.select_related(
        "student",
        "student__campus",
        "route",
        "stop",
        "route__vehicle",
        "route__driver",
    )
    campus_scope = get_user_campus_scope(user)
    if campus_scope:
        queryset = queryset.filter(student__campus=campus_scope)
    return queryset


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


@admin_portal_required
def notice_list(request):
    q = (request.GET.get("q") or "").strip()
    notification_type = (request.GET.get("type") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    assignments = _assignment_queryset_for(request.user)
    notices = ParentNotification.objects.select_related(
        "assignment",
        "assignment__student",
        "assignment__student__campus",
        "assignment__route",
    ).filter(assignment__in=assignments)
    if q:
        notices = notices.filter(
            Q(message__icontains=q)
            | Q(assignment__student__first_name__icontains=q)
            | Q(assignment__student__last_name__icontains=q)
            | Q(assignment__student__student_id__icontains=q)
            | Q(assignment__route__name__icontains=q)
            | Q(assignment__route__code__icontains=q)
        )
    if notification_type:
        notices = notices.filter(notification_type=notification_type)

    paginator = Paginator(notices.order_by("-sent_at"), per_page)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "portals/admin/transport/notices_list.html",
        {
            "notices": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "notification_type": notification_type,
            "notification_types": ParentNotification.TYPE_CHOICES,
            "per_page": per_page,
        },
    )


@admin_portal_required
def notice_create(request):
    template_key = (request.GET.get("template") or "").strip()
    assignment_id = (request.GET.get("assignment") or "").strip()
    initial = {}
    if template_key in NOTICE_TEMPLATES:
        notice_type, message = NOTICE_TEMPLATES[template_key]
        initial.update({"notification_type": notice_type, "message": message})
    if assignment_id:
        initial["assignment"] = assignment_id

    form = ParentNotificationForm(request.POST or None, initial=initial)
    allowed_assignments = _assignment_queryset_for(request.user).filter(is_active=True).order_by(
        "student__last_name",
        "student__first_name",
        "route__code",
    )
    form.fields["assignment"].queryset = allowed_assignments

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Transport notice saved successfully.")
        return redirect("admin_transport_notices_list")

    return render(
        request,
        "portals/admin/transport/notice_form.html",
        {
            "form": form,
            "templates": NOTICE_TEMPLATES,
        },
    )
