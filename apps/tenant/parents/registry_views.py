from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from apps.tenant.portals.permissions import admin_portal_required

from .views import _editable_parents_queryset_for


@admin_portal_required
def parent_list(request):
    q = (request.GET.get("q") or "").strip()
    page_number = request.GET.get("page") or 1
    try:
        per_page = int(request.GET.get("per_page") or 25)
    except (TypeError, ValueError):
        per_page = 25
    per_page = max(1, min(per_page, 200))

    parents_qs = _editable_parents_queryset_for(request.user).prefetch_related(
        "parentstudentlink_set__student",
        "parentstudentlink_set__student__campus",
    )
    if q:
        parents_qs = parents_qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
            | Q(parentstudentlink__student__first_name__icontains=q)
            | Q(parentstudentlink__student__last_name__icontains=q)
            | Q(parentstudentlink__student__student_id__icontains=q)
        ).distinct()

    page_obj = Paginator(parents_qs, per_page).get_page(page_number)
    return render(
        request,
        "portals/admin/parents/list.html",
        {
            "parents": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )
