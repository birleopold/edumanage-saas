from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.academics.models import ClassGroup
from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.teachers.models import TeacherProfile

from .forms import PeriodForm, RoomForm, TimetableEntryForm
from .models import Period, Room, TimetableEntry
from .services import (
    WEEKDAY_ORDER,
    active_entries,
    active_periods,
    annotate_entries_with_clashes,
    base_entry_queryset,
    timetable_matrix,
    weekday_choices,
)


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _campus_filter_q(campus):
    return Q(offering__campus=campus) | Q(offering__campus__isnull=True, offering__class_group__campus=campus)


@admin_portal_required
def timetable_grid(request):
    campus = get_current_campus(request)
    class_group_id = request.GET.get("class_group") or ""
    teacher_id = request.GET.get("teacher") or ""

    entries_qs = active_entries()
    class_groups = ClassGroup.objects.filter(is_active=True).order_by("name")
    teachers = TeacherProfile.objects.filter(is_active=True).order_by("last_name", "first_name")

    if campus:
        entries_qs = entries_qs.filter(_campus_filter_q(campus)).distinct()
        class_groups = class_groups.filter(campus=campus)
        teachers = teachers.filter(campus=campus)

    if class_group_id:
        entries_qs = entries_qs.filter(offering__class_group_id=class_group_id)
    if teacher_id:
        entries_qs = entries_qs.filter(offering__teacher_id=teacher_id)

    periods = list(active_periods())
    entries = annotate_entries_with_clashes(list(entries_qs))
    matrix = timetable_matrix(entries, periods)

    return render(
        request,
        "portals/admin/timetable/grid.html",
        {
            "campus": campus,
            "class_groups": class_groups,
            "teachers": teachers,
            "selected_class_group_id": int(class_group_id) if class_group_id.isdigit() else None,
            "selected_teacher_id": int(teacher_id) if teacher_id.isdigit() else None,
            "periods": periods,
            "weekdays": weekday_choices(),
            "weekday_order": WEEKDAY_ORDER,
            "matrix": matrix,
            "entries": entries,
            "clash_count": sum(1 for entry in entries if entry.clash_count),
        },
    )


@admin_portal_required
def clash_report(request):
    campus = get_current_campus(request)
    entries_qs = active_entries()
    if campus:
        entries_qs = entries_qs.filter(_campus_filter_q(campus)).distinct()
    entries = annotate_entries_with_clashes(list(entries_qs))
    conflicted_entries = [entry for entry in entries if entry.clash_count]

    return render(
        request,
        "portals/admin/timetable/clashes.html",
        {
            "campus": campus,
            "entries": conflicted_entries,
            "clash_count": sum(entry.clash_count for entry in conflicted_entries),
        },
    )


@admin_portal_required
def period_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Period.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q))

    page_obj = Paginator(qs, per_page).get_page(page_number)

    return render(
        request,
        "portals/admin/timetable/periods_list.html",
        {"periods": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def period_create(request):
    if request.method == "POST":
        form = PeriodForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Period created.")
            return redirect("admin_periods_list")
    else:
        form = PeriodForm()

    return render(request, "portals/admin/timetable/period_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def period_edit(request, pk: int):
    obj = get_object_or_404(Period, pk=pk)
    if request.method == "POST":
        form = PeriodForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Period updated.")
            return redirect("admin_periods_list")
    else:
        form = PeriodForm(instance=obj)

    return render(
        request,
        "portals/admin/timetable/period_form.html",
        {"form": form, "mode": "edit", "period": obj},
    )


@admin_portal_required
def room_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Room.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    page_obj = Paginator(qs, per_page).get_page(page_number)

    return render(
        request,
        "portals/admin/timetable/rooms_list.html",
        {"rooms": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def room_create(request):
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Room created.")
            return redirect("admin_rooms_list")
    else:
        form = RoomForm()

    return render(request, "portals/admin/timetable/room_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def room_edit(request, pk: int):
    obj = get_object_or_404(Room, pk=pk)
    if request.method == "POST":
        form = RoomForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Room updated.")
            return redirect("admin_rooms_list")
    else:
        form = RoomForm(instance=obj)

    return render(
        request,
        "portals/admin/timetable/room_form.html",
        {"form": form, "mode": "edit", "room": obj},
    )


@admin_portal_required
def entry_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1
    clashes_only = request.GET.get("clashes") == "1"
    campus = get_current_campus(request)

    qs = base_entry_queryset()
    if campus:
        qs = qs.filter(_campus_filter_q(campus)).distinct()

    if q:
        qs = qs.filter(
            Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
            | Q(offering__class_group__name__icontains=q)
            | Q(offering__teacher__first_name__icontains=q)
            | Q(offering__teacher__last_name__icontains=q)
            | Q(room__name__icontains=q)
            | Q(room__code__icontains=q)
        )

    entries_all = annotate_entries_with_clashes(list(qs.order_by("weekday", "period__order", "period__name")))
    if clashes_only:
        entries_all = [entry for entry in entries_all if entry.clash_count]

    page_obj = Paginator(entries_all, per_page).get_page(page_number)

    return render(
        request,
        "portals/admin/timetable/entries_list.html",
        {
            "entries": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "clashes_only": clashes_only,
            "clash_count": sum(1 for entry in entries_all if entry.clash_count),
        },
    )


@admin_portal_required
def entry_create(request):
    if request.method == "POST":
        form = TimetableEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Timetable entry created.")
            return redirect("admin_timetable_entries_list")
    else:
        form = TimetableEntryForm()

    return render(request, "portals/admin/timetable/entry_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def entry_edit(request, pk: int):
    obj = get_object_or_404(TimetableEntry, pk=pk)
    if request.method == "POST":
        form = TimetableEntryForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Timetable entry updated.")
            return redirect("admin_timetable_entries_list")
    else:
        form = TimetableEntryForm(instance=obj)

    return render(
        request,
        "portals/admin/timetable/entry_form.html",
        {"form": form, "mode": "edit", "entry": obj},
    )
