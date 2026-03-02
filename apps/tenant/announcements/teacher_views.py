from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import Announcement


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.TEACHER)
def announcement_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Announcement.objects.filter(is_active=True).filter(
        Q(audience=Announcement.ALL) | Q(audience=Announcement.TEACHERS)
    )

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/teacher/announcements/list.html",
        {"announcements": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )
