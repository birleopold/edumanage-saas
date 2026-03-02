from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import StudentTransportAssignment


@role_required(Role.STUDENT)
def my_transport(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    assignments = (
        StudentTransportAssignment.objects.select_related("route", "stop", "route__vehicle")
        .filter(student=student)
        .order_by("-created_at")
    )

    return render(
        request,
        "portals/student/transport/home.html",
        {"student": student, "assignments": assignments},
    )
