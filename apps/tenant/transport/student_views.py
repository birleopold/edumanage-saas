from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import RouteSchedule, StudentTransportAssignment, VehicleTracking


@role_required(Role.STUDENT)
def my_transport(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignments = (
        StudentTransportAssignment.objects.select_related(
            "route",
            "stop",
            "route__vehicle",
            "route__driver",
        )
        .filter(student=student)
        .order_by("-created_at")
    )

    return render(
        request,
        "portals/student/transport/home.html",
        {"student": student, "assignments": assignments},
    )


@role_required(Role.STUDENT)
def assignment_detail(request, pk: int):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignment = get_object_or_404(
        StudentTransportAssignment.objects.select_related(
            "student",
            "route",
            "stop",
            "route__vehicle",
            "route__driver",
        ),
        pk=pk,
        student=student,
    )

    latest_tracking = None
    if assignment.route.vehicle_id:
        latest_tracking = (
            VehicleTracking.objects.filter(vehicle_id=assignment.route.vehicle_id)
            .order_by("-timestamp")
            .first()
        )
    schedules = RouteSchedule.objects.filter(route=assignment.route, is_active=True).order_by(
        "day_of_week",
        "start_time",
    )

    return render(
        request,
        "portals/student/transport/detail.html",
        {
            "student": student,
            "assignment": assignment,
            "latest_tracking": latest_tracking,
            "schedules": schedules,
        },
    )
