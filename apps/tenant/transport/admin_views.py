from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import (
    RouteStopForm,
    StudentTransportAssignmentForm,
    TransportRouteForm,
    VehicleForm,
)
from .models import RouteStop, StudentTransportAssignment, TransportRoute, Vehicle


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.ADMIN)
def vehicle_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Vehicle.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(plate_number__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/vehicles_list.html",
        {"vehicles": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def vehicle_create(request):
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_vehicles_list")
    else:
        form = VehicleForm()

    return render(request, "portals/admin/transport/vehicle_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def vehicle_edit(request, pk: int):
    obj = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        form = VehicleForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_vehicles_list")
    else:
        form = VehicleForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/vehicle_form.html",
        {"form": form, "mode": "edit", "vehicle": obj},
    )


@role_required(Role.ADMIN)
def route_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = TransportRoute.objects.select_related("vehicle").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(vehicle__name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/routes_list.html",
        {"routes": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def route_create(request):
    if request.method == "POST":
        form = TransportRouteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_routes_list")
    else:
        form = TransportRouteForm()

    return render(request, "portals/admin/transport/route_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def route_edit(request, pk: int):
    obj = get_object_or_404(TransportRoute, pk=pk)

    if request.method == "POST":
        form = TransportRouteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_routes_list")
    else:
        form = TransportRouteForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/route_form.html",
        {"form": form, "mode": "edit", "route": obj},
    )


@role_required(Role.ADMIN)
def stop_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = RouteStop.objects.select_related("route").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(route__name__icontains=q) | Q(route__code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/stops_list.html",
        {"stops": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def stop_create(request):
    if request.method == "POST":
        form = RouteStopForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_stops_list")
    else:
        form = RouteStopForm()

    return render(request, "portals/admin/transport/stop_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def stop_edit(request, pk: int):
    obj = get_object_or_404(RouteStop, pk=pk)

    if request.method == "POST":
        form = RouteStopForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_stops_list")
    else:
        form = RouteStopForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/stop_form.html",
        {"form": form, "mode": "edit", "stop": obj},
    )


@role_required(Role.ADMIN)
def assignment_list(request):
    q = (request.GET.get("q") or "").strip()
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

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/transport/assignments_list.html",
        {"assignments": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def assignment_create(request):
    if request.method == "POST":
        form = StudentTransportAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_assignments_list")
    else:
        form = StudentTransportAssignmentForm()

    return render(
        request,
        "portals/admin/transport/assignment_form.html",
        {"form": form, "mode": "create"},
    )


@role_required(Role.ADMIN)
def assignment_edit(request, pk: int):
    obj = get_object_or_404(StudentTransportAssignment, pk=pk)

    if request.method == "POST":
        form = StudentTransportAssignmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_transport_assignments_list")
    else:
        form = StudentTransportAssignmentForm(instance=obj)

    return render(
        request,
        "portals/admin/transport/assignment_form.html",
        {"form": form, "mode": "edit", "assignment": obj},
    )
