from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile

from .models import Stream


def _accessible_streams(request):
    qs = Stream.objects.filter(is_active=True).select_related(
        "class_group",
        "class_group__campus",
        "class_teacher",
    )
    scoped = get_user_campus_scope(request.user)
    if scoped is not None:
        return qs.filter(class_group__campus=scoped)

    current = get_current_campus(request)
    if current is not None:
        qs = qs.filter(class_group__campus=current)
    return qs


def _eligible_students(target_stream, q=""):
    """Return learners that can safely move into the target stream.

    A stream assignment must not be used as an accidental class promotion.
    Learners therefore need to be unassigned or already in a sibling stream of
    the same class group. Campus must also match whenever the class has one.
    """

    qs = StudentProfile.objects.filter(is_active=True).select_related(
        "campus",
        "stream",
        "stream__class_group",
    )
    class_group = target_stream.class_group
    if class_group.campus_id:
        qs = qs.filter(campus_id=class_group.campus_id)
    qs = qs.filter(Q(stream__isnull=True) | Q(stream__class_group=class_group))
    if q:
        qs = qs.filter(
            Q(student_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    return qs.order_by("last_name", "first_name", "student_id")


def _redirect_url(stream_id, q="", per_page=50):
    params = {"stream": stream_id, "per_page": per_page}
    if q:
        params["q"] = q
    return reverse("admin_stream_bulk_assignment") + "?" + urlencode(params)


@admin_portal_required
def bulk_stream_assignment(request):
    stream_id = request.GET.get("stream") or request.POST.get("stream")
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    try:
        per_page = int(request.GET.get("per_page") or request.POST.get("per_page") or 50)
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(10, min(per_page, 200))

    streams = _accessible_streams(request).order_by("class_group__name", "name")
    target_stream = streams.filter(pk=stream_id).first() if stream_id else None
    students_qs = _eligible_students(target_stream, q) if target_stream else StudentProfile.objects.none()

    if request.method == "POST":
        if target_stream is None:
            messages.error(request, "Select an accessible target stream before assigning learners.")
            return redirect("admin_stream_bulk_assignment")

        raw_ids = request.POST.getlist("student_ids")
        try:
            selected_ids = sorted({int(value) for value in raw_ids})
        except (TypeError, ValueError):
            selected_ids = []

        if not selected_ids:
            messages.warning(request, "Select at least one learner to assign.")
            return redirect(_redirect_url(target_stream.pk, q, per_page))

        # Validate the entire selection before making any changes. This also
        # prevents a crafted POST from moving a learner from another campus or
        # another class group.
        eligible_ids = set(students_qs.filter(pk__in=selected_ids).values_list("pk", flat=True))
        if eligible_ids != set(selected_ids):
            messages.error(
                request,
                "One or more selected learners are outside this stream's campus or class group. No changes were made.",
            )
            return redirect(_redirect_url(target_stream.pk, q, per_page))

        with transaction.atomic():
            locked_stream = (
                _accessible_streams(request)
                .select_for_update()
                .get(pk=target_stream.pk)
            )
            locked_students = list(
                _eligible_students(locked_stream)
                .select_for_update()
                .filter(pk__in=selected_ids)
                .order_by("pk")
            )
            if {item.pk for item in locked_students} != set(selected_ids):
                messages.error(request, "The eligible learner list changed. No assignments were saved; try again.")
                transaction.set_rollback(True)
                return redirect(_redirect_url(locked_stream.pk, q, per_page))

            current_count = StudentProfile.objects.filter(stream=locked_stream, is_active=True).count()
            moving = [student for student in locked_students if student.stream_id != locked_stream.pk]
            available_places = max(int(locked_stream.capacity) - current_count, 0)
            if len(moving) > available_places:
                messages.error(
                    request,
                    f"{locked_stream} has {available_places} place(s) available, but {len(moving)} learner(s) would be moved. No changes were made.",
                )
                transaction.set_rollback(True)
                return redirect(_redirect_url(locked_stream.pk, q, per_page))

            moved = 0
            already_assigned = 0
            for student in locked_students:
                if student.stream_id == locked_stream.pk:
                    already_assigned += 1
                    continue
                previous_stream = student.stream
                student.stream = locked_stream
                student.save(update_fields=["stream"])
                moved += 1
                log_action(
                    student,
                    action="STREAM_ASSIGNED" if previous_stream is None else "STREAM_CHANGED",
                    description=f"Assigned learner to {locked_stream} through bulk stream placement.",
                    user=request.user,
                    metadata={
                        "previous_stream_id": getattr(previous_stream, "pk", None),
                        "previous_stream": str(previous_stream) if previous_stream else "",
                        "target_stream_id": locked_stream.pk,
                        "target_stream": str(locked_stream),
                        "class_group_id": locked_stream.class_group_id,
                        "campus_id": locked_stream.class_group.campus_id,
                        "source": "bulk_stream_assignment",
                    },
                )

        messages.success(
            request,
            f"Stream assignment complete. Moved {moved} learner(s); {already_assigned} were already in {target_stream.name}.",
        )
        return redirect(_redirect_url(target_stream.pk, q, per_page))

    paginator = Paginator(students_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    current_count = target_stream.get_student_count() if target_stream else 0
    remaining_capacity = max(target_stream.capacity - current_count, 0) if target_stream else 0

    return render(
        request,
        "portals/admin/academics/stream_bulk_assignment.html",
        {
            "streams": streams,
            "target_stream": target_stream,
            "students": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "current_count": current_count,
            "remaining_capacity": remaining_capacity,
        },
    )
