from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import BedAllocationForm, BedForm, HostelForm, HostelRoomForm
from .models import Bed, BedAllocation, Hostel, HostelRoom


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
def hostel_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Hostel.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hostels/hostels_list.html",
        {"hostels": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def hostel_create(request):
    if request.method == "POST":
        form = HostelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_hostels_list")
    else:
        form = HostelForm()

    return render(request, "portals/admin/hostels/hostel_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def hostel_edit(request, pk: int):
    obj = get_object_or_404(Hostel, pk=pk)

    if request.method == "POST":
        form = HostelForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_hostels_list")
    else:
        form = HostelForm(instance=obj)

    return render(
        request,
        "portals/admin/hostels/hostel_form.html",
        {"form": form, "mode": "edit", "hostel": obj},
    )


@role_required(Role.ADMIN)
def room_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = HostelRoom.objects.select_related("hostel").all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(hostel__name__icontains=q) | Q(hostel__code__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hostels/rooms_list.html",
        {"rooms": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def room_create(request):
    if request.method == "POST":
        form = HostelRoomForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_hostel_rooms_list")
    else:
        form = HostelRoomForm()

    return render(request, "portals/admin/hostels/room_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def room_edit(request, pk: int):
    obj = get_object_or_404(HostelRoom, pk=pk)

    if request.method == "POST":
        form = HostelRoomForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_hostel_rooms_list")
    else:
        form = HostelRoomForm(instance=obj)

    return render(
        request,
        "portals/admin/hostels/room_form.html",
        {"form": form, "mode": "edit", "room": obj},
    )


@role_required(Role.ADMIN)
def bed_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Bed.objects.select_related("room", "room__hostel").all()
    if q:
        qs = qs.filter(
            Q(label__icontains=q) | Q(room__name__icontains=q) | Q(room__hostel__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hostels/beds_list.html",
        {"beds": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def bed_create(request):
    if request.method == "POST":
        form = BedForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_hostel_beds_list")
    else:
        form = BedForm()

    return render(request, "portals/admin/hostels/bed_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def bed_edit(request, pk: int):
    obj = get_object_or_404(Bed, pk=pk)

    if request.method == "POST":
        form = BedForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_hostel_beds_list")
    else:
        form = BedForm(instance=obj)

    return render(
        request,
        "portals/admin/hostels/bed_form.html",
        {"form": form, "mode": "edit", "bed": obj},
    )


@role_required(Role.ADMIN)
def allocation_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = BedAllocation.objects.select_related(
        "student",
        "bed",
        "bed__room",
        "bed__room__hostel",
    ).all()

    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(bed__label__icontains=q)
            | Q(bed__room__name__icontains=q)
            | Q(bed__room__hostel__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hostels/allocations_list.html",
        {"allocations": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def allocation_create(request):
    if request.method == "POST":
        form = BedAllocationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_bed_allocations_list")
    else:
        form = BedAllocationForm()

    return render(
        request,
        "portals/admin/hostels/allocation_form.html",
        {"form": form, "mode": "create"},
    )


@role_required(Role.ADMIN)
def allocation_edit(request, pk: int):
    obj = get_object_or_404(BedAllocation, pk=pk)

    if request.method == "POST":
        form = BedAllocationForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_bed_allocations_list")
    else:
        form = BedAllocationForm(instance=obj)

    return render(
        request,
        "portals/admin/hostels/allocation_form.html",
        {"form": form, "mode": "edit", "allocation": obj},
    )
