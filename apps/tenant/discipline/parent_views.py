from django.core.paginator import Paginator
from django.db.models import Q
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

from .models import Incident


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.PARENT)
def child_incidents(request):
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

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Incident.objects.filter(student_id__in=student_ids).select_related("student", "reported_by")

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(category__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/parent/discipline/incidents_list.html",
        {
            "parent": parent,
            "incidents": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )
