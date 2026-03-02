from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import BedAllocation


@role_required(Role.STUDENT)
def my_hostel(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    allocations = (
        BedAllocation.objects.select_related("bed", "bed__room", "bed__room__hostel")
        .filter(student=student)
        .order_by("-created_at")
    )

    current = allocations.filter(status=BedAllocation.ACTIVE).first()

    return render(
        request,
        "portals/student/hostels/home.html",
        {"student": student, "current": current, "allocations": allocations},
    )
