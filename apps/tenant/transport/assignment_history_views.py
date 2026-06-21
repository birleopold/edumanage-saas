from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.permissions import admin_portal_required

from .models import StudentTransportAssignment


@admin_portal_required
def assignment_detail(request, pk: int):
    assignment = get_object_or_404(
        StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle", "route__driver"),
        pk=pk,
    )
    return render(request, "portals/admin/transport/assignment_detail.html", {"assignment": assignment})
