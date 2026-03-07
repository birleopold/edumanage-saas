from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from apps.tenant.students.models import StudentProfile

from .forms import ActivityForm
from .models import Activity, ActivityMember


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
def activity_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Activity.objects.select_related("campus", "head").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/activities/list.html",
        {
            "activities": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "activities_create_url": reverse("admin_activities_create"),
        },
    )


@role_required(Role.ADMIN)
def activity_create(request):
    if request.method == "POST":
        form = ActivityForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Activity created.")
            return redirect("admin_activities_list")
    else:
        form = ActivityForm()

    return render(request, "portals/admin/activities/form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def activity_edit(request, pk: int):
    obj = get_object_or_404(Activity, pk=pk)

    if request.method == "POST":
        form = ActivityForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Activity updated.")
            return redirect("admin_activities_list")
    else:
        form = ActivityForm(instance=obj)

    return render(
        request,
        "portals/admin/activities/form.html",
        {"form": form, "mode": "edit", "activity": obj},
    )


@role_required(Role.ADMIN)
def activity_members(request, pk: int):
    obj = get_object_or_404(Activity, pk=pk)

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    members_qs = (
        ActivityMember.objects.select_related("student", "student__stream", "student__campus")
        .filter(activity=obj, is_active=True)
        .order_by("student__last_name", "student__first_name")
    )

    if q:
        members_qs = members_qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
        )

    paginator = Paginator(members_qs, per_page)
    page_obj = paginator.get_page(page_number)

    # For quick add: show a limited list of students (optional), but support student_id lookup
    student_q = (request.GET.get("student_q") or "").strip()
    student_results = StudentProfile.objects.select_related("stream", "campus").filter(is_active=True)
    if obj.campus_id:
        student_results = student_results.filter(campus_id=obj.campus_id)
    if student_q:
        student_results = student_results.filter(
            Q(first_name__icontains=student_q)
            | Q(last_name__icontains=student_q)
            | Q(student_id__icontains=student_q)
        )
    else:
        student_results = student_results.none()

    return render(
        request,
        "portals/admin/activities/members.html",
        {
            "activity": obj,
            "members": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "student_q": student_q,
            "student_results": student_results[:25],
        },
    )


@role_required(Role.ADMIN)
def activity_member_add(request, pk: int):
    obj = get_object_or_404(Activity, pk=pk)

    if request.method != "POST":
        return redirect("admin_activities_members", pk=obj.pk)

    student_id = request.POST.get("student_id")
    if not student_id:
        messages.error(request, "Please select a student.")
        return redirect("admin_activities_members", pk=obj.pk)

    student = get_object_or_404(StudentProfile, pk=student_id)

    membership, created = ActivityMember.objects.get_or_create(activity=obj, student=student)
    if not created and not membership.is_active:
        membership.is_active = True
        membership.save(update_fields=["is_active"])

    messages.success(request, "Student added to activity.")
    return redirect("admin_activities_members", pk=obj.pk)


@role_required(Role.ADMIN)
def activity_member_remove(request, pk: int, member_id: int):
    obj = get_object_or_404(Activity, pk=pk)
    membership = get_object_or_404(ActivityMember, pk=member_id, activity=obj)
    membership.is_active = False
    membership.save(update_fields=["is_active"])
    messages.success(request, "Student removed from activity.")
    return redirect("admin_activities_members", pk=obj.pk)
