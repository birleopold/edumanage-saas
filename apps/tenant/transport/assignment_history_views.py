from django.shortcuts import get_object_or_404, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .models import StudentTransportAssignment


def _assignment_queryset_for(user):
    qs = StudentTransportAssignment.objects.select_related("student", "student__campus", "route", "stop", "route__vehicle", "route__driver")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(student__campus=scoped)
    return qs


@admin_portal_required
def assignment_detail(request, pk: int):
    assignment = get_object_or_404(
        _assignment_queryset_for(request.user),
        pk=pk,
    )
    return render(request, "portals/admin/transport/assignment_detail.html", {"assignment": assignment})
