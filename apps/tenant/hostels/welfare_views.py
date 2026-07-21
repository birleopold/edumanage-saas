from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required, role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import (
    BoardingLeave,
    BoardingProfile,
    HostelRollCall,
    HostelRollCallEntry,
    WelfareCase,
)
from .welfare_forms import (
    BoardingLeaveForm,
    BoardingProfileForm,
    HostelRollCallForm,
    WelfareCaseActionForm,
    WelfareCaseForm,
)
from .welfare_services import (
    approve_leave,
    boarding_welfare_readiness,
    bootstrap_boarding_profiles,
    complete_roll_call,
    populate_roll_call,
    record_departure,
    record_return,
    student_welfare_timeline,
)


def _is_full_admin(user):
    return bool(user.is_superuser or (hasattr(user, "has_role") and user.has_role(Role.ADMIN)))


def _parse_per_page(request, default=25, maximum=200):
    try:
        value = int(request.GET.get("per_page") or default)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _student_queryset_for(user):
    queryset = StudentProfile.objects.select_related("campus", "stream", "stream__class_group")
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(campus=campus)
    return queryset


def _profile_queryset_for(user):
    queryset = BoardingProfile.objects.select_related("student", "student__campus")
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(student__campus=campus)
    return queryset


def _leave_queryset_for(user):
    queryset = BoardingLeave.objects.select_related(
        "student",
        "student__campus",
        "bed_allocation",
        "bed_allocation__bed",
        "bed_allocation__bed__room",
        "bed_allocation__bed__room__hostel",
        "approved_by",
        "recorded_by",
    )
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(student__campus=campus)
    return queryset


def _case_queryset_for(user):
    queryset = WelfareCase.objects.select_related(
        "student",
        "student__campus",
        "campus",
        "assigned_to",
        "opened_by",
        "linked_sickbay_visit",
        "linked_discipline_incident",
        "linked_bed_allocation",
    )
    campus = get_user_campus_scope(user)
    if campus:
        queryset = queryset.filter(student__campus=campus)
    if not _is_full_admin(user):
        queryset = queryset.filter(
            Q(confidential=False) | Q(assigned_to=user) | Q(opened_by=user)
        )
    return queryset


@role_required(Role.ADMIN)
def welfare_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "bootstrap_profiles":
        summary = bootstrap_boarding_profiles(dry_run=False)
        messages.success(
            request,
            f"Boarding profiles created: {summary['created_count']}; existing: {summary['existing_count']}. "
            "No bed allocations or learner placements were changed.",
        )
        return redirect("admin_boarding_welfare_dashboard")
    readiness = boarding_welfare_readiness()
    recent_cases = _case_queryset_for(request.user)[:10]
    recent_leaves = _leave_queryset_for(request.user)[:10]
    recent_roll_calls = HostelRollCall.objects.select_related("hostel", "recorded_by")[:10]
    return render(
        request,
        "portals/admin/hostels/welfare/dashboard.html",
        {
            "readiness": readiness,
            "recent_cases": recent_cases,
            "recent_leaves": recent_leaves,
            "recent_roll_calls": recent_roll_calls,
        },
    )


@role_required(Role.ADMIN)
def boarding_profile_list(request):
    q = (request.GET.get("q") or "").strip()
    queryset = _profile_queryset_for(request.user)
    if q:
        queryset = queryset.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(primary_guardian_name__icontains=q)
        )
    paginator = Paginator(queryset, _parse_per_page(request))
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/hostels/welfare/profiles.html",
        {"profiles": page_obj.object_list, "page_obj": page_obj, "q": q},
    )


@role_required(Role.ADMIN)
def boarding_profile_create(request):
    campus = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = BoardingProfileForm(request.POST, campus_scope=campus)
        if form.is_valid():
            profile = form.save()
            messages.success(request, "Boarding profile created.")
            return redirect("admin_boarding_student_timeline", student_pk=profile.student_id)
    else:
        form = BoardingProfileForm(campus_scope=campus)
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {"form": form, "title": "Add boarding profile", "back_url_name": "admin_boarding_profiles"},
    )


@role_required(Role.ADMIN)
def boarding_profile_edit(request, pk):
    profile = get_object_or_404(_profile_queryset_for(request.user), pk=pk)
    campus = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = BoardingProfileForm(request.POST, instance=profile, campus_scope=campus)
        if form.is_valid():
            form.save()
            messages.success(request, "Boarding profile updated.")
            return redirect("admin_boarding_student_timeline", student_pk=profile.student_id)
    else:
        form = BoardingProfileForm(instance=profile, campus_scope=campus)
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {"form": form, "title": "Edit boarding profile", "back_url_name": "admin_boarding_profiles"},
    )


@admin_portal_required
def student_welfare_detail(request, student_pk):
    student = get_object_or_404(_student_queryset_for(request.user), pk=student_pk)
    profile = BoardingProfile.objects.filter(student=student).first()
    return render(
        request,
        "portals/admin/hostels/welfare/student_timeline.html",
        {
            "student": student,
            "profile": profile,
            "timeline": student_welfare_timeline(student),
            "open_cases": _case_queryset_for(request.user).filter(student=student).exclude(
                status__in=[WelfareCase.RESOLVED, WelfareCase.CLOSED]
            ),
        },
    )


@admin_portal_required
def boarding_leave_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    queryset = _leave_queryset_for(request.user)
    if q:
        queryset = queryset.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(destination__icontains=q)
        )
    if status:
        queryset = queryset.filter(status=status)
    paginator = Paginator(queryset, _parse_per_page(request))
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/hostels/welfare/leaves.html",
        {
            "leaves": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "status_filter": status,
            "status_choices": BoardingLeave.STATUS_CHOICES,
        },
    )


@admin_portal_required
def boarding_leave_create(request):
    campus = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = BoardingLeaveForm(request.POST, campus_scope=campus)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.recorded_by = request.user
            leave.save()
            messages.success(request, "Boarding leave request recorded for approval.")
            return redirect("admin_boarding_leave_detail", pk=leave.pk)
    else:
        form = BoardingLeaveForm(campus_scope=campus)
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {"form": form, "title": "Record boarding leave", "back_url_name": "admin_boarding_leaves"},
    )


@admin_portal_required
def boarding_leave_detail(request, pk):
    leave = get_object_or_404(_leave_queryset_for(request.user), pk=pk)
    return render(request, "portals/admin/hostels/welfare/leave_detail.html", {"leave": leave})


@admin_portal_required
def boarding_leave_transition(request, pk, action):
    if request.method != "POST":
        raise Http404
    leave = get_object_or_404(_leave_queryset_for(request.user), pk=pk)
    try:
        if action == "approve":
            approve_leave(leave, request.user)
            message = "Leave approved."
        elif action == "depart":
            record_departure(leave, request.user, handover_to=request.POST.get("handover_to", ""))
            message = "Learner departure recorded."
        elif action == "return":
            record_return(leave, request.user, note=request.POST.get("return_note", ""))
            message = "Learner return recorded."
        else:
            raise Http404
        messages.success(request, message)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("admin_boarding_leave_detail", pk=leave.pk)


@admin_portal_required
def hostel_roll_call_list(request):
    queryset = HostelRollCall.objects.select_related("hostel", "recorded_by")
    paginator = Paginator(queryset, _parse_per_page(request))
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/hostels/welfare/roll_calls.html",
        {"roll_calls": page_obj.object_list, "page_obj": page_obj},
    )


@admin_portal_required
def hostel_roll_call_create(request):
    if request.method == "POST":
        form = HostelRollCallForm(request.POST)
        if form.is_valid():
            roll_call = form.save(commit=False)
            roll_call.recorded_by = request.user
            roll_call.save()
            populate_roll_call(roll_call, dry_run=False)
            messages.success(request, "Roll call created with the current hostel roster. Presence remains unmarked until recorded.")
            return redirect("admin_hostel_roll_call_detail", pk=roll_call.pk)
    else:
        form = HostelRollCallForm()
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {"form": form, "title": "Create hostel roll call", "back_url_name": "admin_hostel_roll_calls"},
    )


@admin_portal_required
def hostel_roll_call_detail(request, pk):
    roll_call = get_object_or_404(
        HostelRollCall.objects.select_related("hostel", "recorded_by").prefetch_related(
            "entries__student",
            "entries__bed_allocation__bed__room",
            "entries__boarding_leave",
        ),
        pk=pk,
    )
    if request.method == "POST" and roll_call.status != HostelRollCall.LOCKED:
        valid_presence = {choice[0] for choice in HostelRollCallEntry.PRESENCE_CHOICES}
        for entry in roll_call.entries.all():
            presence = request.POST.get(f"presence_{entry.pk}")
            note = request.POST.get(f"note_{entry.pk}", "").strip()
            if presence in valid_presence:
                entry.presence = presence
                entry.note = note
                entry.save(update_fields=["presence", "note", "checked_at"])
        if request.POST.get("action") == "complete":
            try:
                complete_roll_call(roll_call)
                messages.success(request, "Roll call completed.")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Roll-call entries saved.")
        return redirect("admin_hostel_roll_call_detail", pk=roll_call.pk)
    return render(
        request,
        "portals/admin/hostels/welfare/roll_call_detail.html",
        {"roll_call": roll_call, "presence_choices": HostelRollCallEntry.PRESENCE_CHOICES},
    )


@admin_portal_required
def hostel_roll_call_populate(request, pk):
    if request.method != "POST":
        raise Http404
    roll_call = get_object_or_404(HostelRollCall, pk=pk)
    try:
        summary = populate_roll_call(roll_call, dry_run=False)
        messages.success(request, f"Roster refreshed: {summary['created_count']} missing learner(s) added.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("admin_hostel_roll_call_detail", pk=roll_call.pk)


@admin_portal_required
def welfare_case_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    queryset = _case_queryset_for(request.user)
    if q:
        queryset = queryset.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(title__icontains=q)
            | Q(summary__icontains=q)
        )
    if status:
        queryset = queryset.filter(status=status)
    paginator = Paginator(queryset, _parse_per_page(request))
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/hostels/welfare/cases.html",
        {
            "cases": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "status_filter": status,
            "status_choices": WelfareCase.STATUS_CHOICES,
        },
    )


@admin_portal_required
def welfare_case_create(request):
    campus = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = WelfareCaseForm(request.POST, campus_scope=campus)
        if form.is_valid():
            case = form.save(commit=False)
            case.opened_by = request.user
            case.save()
            messages.success(request, "Welfare case opened.")
            return redirect("admin_welfare_case_detail", pk=case.pk)
    else:
        form = WelfareCaseForm(campus_scope=campus)
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {"form": form, "title": "Open welfare case", "back_url_name": "admin_welfare_cases"},
    )


@admin_portal_required
def welfare_case_edit(request, pk):
    case = get_object_or_404(_case_queryset_for(request.user), pk=pk)
    campus = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = WelfareCaseForm(request.POST, instance=case, campus_scope=campus)
        if form.is_valid():
            form.save()
            messages.success(request, "Welfare case updated.")
            return redirect("admin_welfare_case_detail", pk=case.pk)
    else:
        form = WelfareCaseForm(instance=case, campus_scope=campus)
    return render(
        request,
        "portals/admin/hostels/welfare/form.html",
        {"form": form, "title": "Edit welfare case", "back_url_name": "admin_welfare_case_detail", "back_url_pk": case.pk},
    )


@admin_portal_required
def welfare_case_detail(request, pk):
    case = get_object_or_404(_case_queryset_for(request.user).prefetch_related("actions__performed_by"), pk=pk)
    if request.method == "POST":
        form = WelfareCaseActionForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.welfare_case = case
            action.performed_by = request.user
            action.save()
            messages.success(request, "Welfare action recorded.")
            return redirect("admin_welfare_case_detail", pk=case.pk)
    else:
        form = WelfareCaseActionForm()
    return render(
        request,
        "portals/admin/hostels/welfare/case_detail.html",
        {"case": case, "action_form": form},
    )
