from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.orgsettings.services import (
    campus_queryset,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import StudentTransportAssignment


@role_required(Role.PARENT)
def children_transport(request):
    update_current_campus_from_request(request)

    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    campuses = campus_queryset()
    campus_id = selected_campus_id_from_request(request)

    links_qs = ParentStudentLink.objects.filter(parent=parent)
    if campus_id:
        links_qs = links_qs.filter(student__campus_id=campus_id)
    student_ids = list(links_qs.values_list("student_id", flat=True))

    assignments = (
        StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle")
        .filter(student_id__in=student_ids)
        .order_by("student__last_name", "student__first_name", "-created_at")
    )

    return render(
        request,
        "portals/parent/transport/home.html",
        {"parent": parent, "assignments": assignments, "campuses": campuses, "selected_campus_id": campus_id},
    )
