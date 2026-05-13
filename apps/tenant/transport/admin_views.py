from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from django.contrib import messages

from .forms import (
    DriverForm,
    RouteScheduleForm,
    RouteStopForm,
    StudentTransportAssignmentForm,
    TransportRouteForm,
    VehicleForm,
)
from .models import Driver, RouteSchedule, RouteStop, StudentTransportAssignment, TransportRoute, Vehicle, VehicleTracking


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@admin_portal_required
def driver_list(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Driver.objects.select_related("staff").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(license_number__icontains=q) | Q(staff__first_name__icontains=q) | Q(staff__last_name__icontains=q))
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/drivers_list.html",
        {"drivers": page_obj.object_list, "page_obj": page_obj, "q": q, "status_filter": status_filter, "per_page": per_page},
    )


@admin_portal_required
def driver_create(request):
    if request.method == "POST":
        form = DriverForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Driver created successfully.")
            return redirect("admin_transport_drivers_list")
    else:
        form = DriverForm()

    return render(request, "portals/admin/transport/driver_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def driver_edit(request, pk: int):
    obj = get_object_or_404(Driver, pk=pk)

    if request.method == "POST":
        form = DriverForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Driver updated successfully.")
            return redirect("admin_transport_drivers_list")
    else:
        form = DriverForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/driver_form.html",
        {"form": form, "mode": "edit", "driver": obj},
    )


@admin_portal_required
def vehicle_list(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Vehicle.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(plate_number__icontains=q) | Q(model__icontains=q))
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/vehicles_list.html",
        {"vehicles": page_obj.object_list, "page_obj": page_obj, "q": q, "status_filter": status_filter, "per_page": per_page},
    )


@admin_portal_required
def vehicle_create(request):
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Vehicle created successfully.")
            return redirect("admin_transport_vehicles_list")
    else:
        form = VehicleForm()

    return render(request, "portals/admin/transport/vehicle_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def vehicle_edit(request, pk: int):
    obj = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        form = VehicleForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Vehicle updated successfully.")
            return redirect("admin_transport_vehicles_list")
    else:
        form = VehicleForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/vehicle_form.html",
        {"form": form, "mode": "edit", "vehicle": obj},
    )


@admin_portal_required
def vehicle_tracking(request, pk: int):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    # Get latest tracking data
    latest_tracking = VehicleTracking.objects.filter(vehicle=vehicle).order_by("-timestamp").first()
    
    # Get recent tracking history (last 50 records)
    tracking_history = VehicleTracking.objects.filter(vehicle=vehicle).order_by("-timestamp")[:50]

    return render(
        request,
        "portals/admin/transport/vehicle_tracking.html",
        {"vehicle": vehicle, "latest_tracking": latest_tracking, "tracking_history": tracking_history},
    )


@admin_portal_required
def route_list(request):
    q = (request.GET.get("q") or "").strip()
    shift_filter = request.GET.get("shift", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = TransportRoute.objects.select_related("vehicle", "driver").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(vehicle__name__icontains=q))
    if shift_filter:
        qs = qs.filter(shift=shift_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/routes_list.html",
        {"routes": page_obj.object_list, "page_obj": page_obj, "q": q, "shift_filter": shift_filter, "per_page": per_page},
    )


@admin_portal_required
def route_create(request):
    if request.method == "POST":
        form = TransportRouteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Route created successfully.")
            return redirect("admin_transport_routes_list")
    else:
        form = TransportRouteForm()

    return render(request, "portals/admin/transport/route_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def route_edit(request, pk: int):
    obj = get_object_or_404(TransportRoute, pk=pk)

    if request.method == "POST":
        form = TransportRouteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Route updated successfully.")
            return redirect("admin_transport_routes_list")
    else:
        form = TransportRouteForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/route_form.html",
        {"form": form, "mode": "edit", "route": obj},
    )


@admin_portal_required
def route_detail(request, pk: int):
    route = get_object_or_404(TransportRoute.objects.select_related("vehicle", "driver").prefetch_related("stops", "student_assignments__student"), pk=pk)
    
    stops = route.stops.all().order_by("order")
    assignments = route.student_assignments.filter(is_active=True).select_related("student", "stop")
    schedules = RouteSchedule.objects.filter(route=route, is_active=True)

    return render(
        request,
        "portals/admin/transport/route_detail.html",
        {"route": route, "stops": stops, "assignments": assignments, "schedules": schedules},
    )


@admin_portal_required
def stop_list(request):
    q = (request.GET.get("q") or "").strip()
    route_filter = (request.GET.get("route") or "").strip()
    active_filter = request.GET.get("active", "")
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = RouteStop.objects.select_related("route").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(route__name__icontains=q) | Q(route__code__icontains=q))
    if route_filter:
        try:
            qs = qs.filter(route_id=int(route_filter))
        except (TypeError, ValueError):
            pass
    if active_filter == "1":
        qs = qs.filter(is_active=True)
    elif active_filter == "0":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    route_options = TransportRoute.objects.order_by("code", "name")

    return render(
        request,
        "portals/admin/transport/stops_list.html",
        {
            "stops": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "route_filter": route_filter,
            "active_filter": active_filter,
            "routes_for_filter": route_options,
        },
    )


@admin_portal_required
def stop_create(request):
    route_id = request.GET.get("route")
    
    if request.method == "POST":
        form = RouteStopForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Stop created successfully.")
            if route_id:
                return redirect("admin_transport_route_detail", pk=route_id)
            return redirect("admin_transport_stops_list")
    else:
        initial = {}
        if route_id:
            initial["route"] = route_id
        form = RouteStopForm(initial=initial)

    return render(request, "portals/admin/transport/stop_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def stop_edit(request, pk: int):
    obj = get_object_or_404(RouteStop, pk=pk)

    if request.method == "POST":
        form = RouteStopForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Stop updated successfully.")
            return redirect("admin_transport_route_detail", pk=obj.route.pk)
    else:
        form = RouteStopForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/stop_form.html",
        {"form": form, "mode": "edit", "stop": obj},
    )


@admin_portal_required
def assignment_list(request):
    q = (request.GET.get("q") or "").strip()
    route_filter = (request.GET.get("route") or "").strip()
    active_filter = request.GET.get("active", "")
    service_filter = (request.GET.get("service") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle").all()
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(route__name__icontains=q)
            | Q(route__code__icontains=q)
            | Q(stop__name__icontains=q)
        )
    if route_filter:
        try:
            qs = qs.filter(route_id=int(route_filter))
        except (TypeError, ValueError):
            pass
    if active_filter == "1":
        qs = qs.filter(is_active=True)
    elif active_filter == "0":
        qs = qs.filter(is_active=False)

    valid_service = {
        StudentTransportAssignment.PICKUP_ONLY,
        StudentTransportAssignment.DROPOFF_ONLY,
        StudentTransportAssignment.BOTH,
    }
    if service_filter in valid_service:
        qs = qs.filter(service_type=service_filter)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    route_options = TransportRoute.objects.order_by("code", "name")

    return render(
        request,
        "portals/admin/transport/assignments_list.html",
        {
            "assignments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "route_filter": route_filter,
            "active_filter": active_filter,
            "service_filter": service_filter,
            "routes_for_filter": route_options,
            "service_choices": StudentTransportAssignment.SERVICE_TYPE_CHOICES,
        },
    )


@admin_portal_required
def assignment_create(request):
    if request.method == "POST":
        form = StudentTransportAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save()
            messages.success(request, f"Student {assignment.student.get_full_name()} assigned to route {assignment.route.code} successfully.")
            return redirect("admin_transport_assignments_list")
    else:
        form = StudentTransportAssignmentForm()

    return render(
        request,
        "portals/admin/transport/assignment_form.html",
        {"form": form, "mode": "create"},
    )


@admin_portal_required
def assignment_edit(request, pk: int):
    obj = get_object_or_404(StudentTransportAssignment, pk=pk)

    if request.method == "POST":
        form = StudentTransportAssignmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Assignment updated successfully.")
            return redirect("admin_transport_assignments_list")
    else:
        form = StudentTransportAssignmentForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/assignment_form.html",
        {"form": form, "mode": "edit", "assignment": obj},
    )
