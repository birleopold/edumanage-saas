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

from .models import SickbayVisit, StudentMedicalProfile


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    try:
        return max(1, min(int(request.GET.get("per_page", default)), max_value))
    except (TypeError, ValueError):
        return default


@role_required(Role.PARENT)
def child_sickbay_visits(request):
    update_current_campus_from_request(request)

    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    campuses = campus_queryset()
    campus_id = selected_campus_id_from_request(request)
    links_qs = ParentStudentLink.objects.filter(parent=parent).select_related("student")
    if campus_id:
        links_qs = links_qs.filter(student__campus_id=campus_id)
    student_ids = list(links_qs.values_list("student_id", flat=True))

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    qs = SickbayVisit.objects.filter(student_id__in=student_ids).select_related("student", "campus")
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(complaint__icontains=q)
            | Q(symptoms__icontains=q)
            | Q(treatment_given__icontains=q)
        )

    page_obj = Paginator(qs, per_page).get_page(request.GET.get("page") or 1)
    profiles = StudentMedicalProfile.objects.filter(student_id__in=student_ids).select_related("student")

    return render(
        request,
        "portals/parent/sickbay/visits.html",
        {
            "parent": parent,
            "visits": page_obj.object_list,
            "page_obj": page_obj,
            "profiles": profiles,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )
