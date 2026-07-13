from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import SickbayVisit


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    try:
        return max(1, min(int(request.GET.get("per_page", default)), max_value))
    except (TypeError, ValueError):
        return default


@role_required(Role.STUDENT)
def my_sickbay_visits(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    qs = SickbayVisit.objects.filter(student=student).select_related("campus")
    if q:
        qs = qs.filter(
            Q(complaint__icontains=q)
            | Q(symptoms__icontains=q)
            | Q(treatment_given__icontains=q)
            | Q(medicine_given__icontains=q)
        )
    page_obj = Paginator(qs, per_page).get_page(request.GET.get("page") or 1)
    profile = getattr(student, "medical_profile", None)
    return render(
        request,
        "portals/student/sickbay/visits.html",
        {"student": student, "profile": profile, "visits": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )
