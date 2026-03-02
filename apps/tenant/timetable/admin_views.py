from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import PeriodForm, RoomForm, TimetableEntryForm
from .models import Period, Room, TimetableEntry


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
def period_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Period.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/timetable/periods_list.html",
        {"periods": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def period_create(request):
    if request.method == "POST":
        form = PeriodForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_periods_list")
    else:
        form = PeriodForm()

    return render(request, "portals/admin/timetable/period_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def period_edit(request, pk: int):
    obj = get_object_or_404(Period, pk=pk)
    if request.method == "POST":
        form = PeriodForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_periods_list")
    else:
        form = PeriodForm(instance=obj)

    return render(
        request,
        "portals/admin/timetable/period_form.html",
        {"form": form, "mode": "edit", "period": obj},
    )


@role_required(Role.ADMIN)
def room_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Room.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/timetable/rooms_list.html",
        {"rooms": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def room_create(request):
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_rooms_list")
    else:
        form = RoomForm()

    return render(request, "portals/admin/timetable/room_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def room_edit(request, pk: int):
    obj = get_object_or_404(Room, pk=pk)
    if request.method == "POST":
        form = RoomForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_rooms_list")
    else:
        form = RoomForm(instance=obj)

    return render(
        request,
        "portals/admin/timetable/room_form.html",
        {"form": form, "mode": "edit", "room": obj},
    )


@role_required(Role.ADMIN)
def entry_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = TimetableEntry.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "offering__teacher",
        "period",
        "room",
    )

    if q:
        qs = qs.filter(
            Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
            | Q(offering__class_group__name__icontains=q)
            | Q(offering__teacher__first_name__icontains=q)
            | Q(offering__teacher__last_name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/timetable/entries_list.html",
        {"entries": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def entry_create(request):
    if request.method == "POST":
        form = TimetableEntryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_timetable_entries_list")
    else:
        form = TimetableEntryForm()

    return render(request, "portals/admin/timetable/entry_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def entry_edit(request, pk: int):
    obj = get_object_or_404(TimetableEntry, pk=pk)
    if request.method == "POST":
        form = TimetableEntryForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_timetable_entries_list")
    else:
        form = TimetableEntryForm(instance=obj)

    return render(
        request,
        "portals/admin/timetable/entry_form.html",
        {"form": form, "mode": "edit", "entry": obj},
    )
