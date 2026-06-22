from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.orgsettings.services import (
    campus_queryset,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import ParentNotification, RouteSchedule, StudentTransportAssignment, VehicleTracking


def _parent_student_ids(parent, campus_id=None):
    links_qs = ParentStudentLink.objects.filter(parent=parent)
    if campus_id:
        links_qs = links_qs.filter(student__campus_id=campus_id)
    return list(links_qs.values_list("student_id", flat=True))


@role_required(Role.PARENT)
def children_transport(request):
    update_current_campus_from_request(request)

    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    campuses = campus_queryset()
    campus_id = selected_campus_id_from_request(request)
    student_ids = _parent_student_ids(parent, campus_id)

    assignments = (
        StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle", "route__driver")
        .prefetch_related("route__schedules", "notifications")
        .filter(student_id__in=student_ids)
        .order_by("student__last_name", "student__first_name", "-created_at")
    )

    notices = ParentNotification.objects.select_related("assignment", "assignment__student", "assignment__route").filter(assignment__in=assignments).order_by("-sent_at")[:20]

    return render(
        request,
        "portals/parent/transport/home.html",
        {"parent": parent, "assignments": assignments, "notices": notices, "campuses": campuses, "selected_campus_id": campus_id},
    )


@role_required(Role.PARENT)
def assignment_detail(request, pk):
    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    assignment = get_object_or_404(
        StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle", "route__driver"),
        pk=pk,
        student_id__in=_parent_student_ids(parent),
    )
    latest_tracking = None
    if assignment.route.vehicle:
        latest_tracking = VehicleTracking.objects.filter(vehicle=assignment.route.vehicle).order_by("-timestamp").first()
    schedules = RouteSchedule.objects.filter(route=assignment.route, is_active=True).order_by("day_of_week", "start_time")
    notices = assignment.notifications.all().order_by("-sent_at")[:50]
    return render(
        request,
        "portals/parent/transport/detail.html",
        {"assignment": assignment, "latest_tracking": latest_tracking, "schedules": schedules, "notices": notices},
    )
