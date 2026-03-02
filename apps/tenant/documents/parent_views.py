from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from apps.tenant.orgsettings.services import (
    campus_queryset,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .models import Document


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
def document_list(request):
    update_current_campus_from_request(request)

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = campus_queryset()
    campus_id = selected_campus_id_from_request(request)

    qs = Document.objects.filter(is_active=True).filter(
        Q(audience=Document.ALL) | Q(audience=Document.PARENTS)
    )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/parent/documents/list.html",
        {
            "documents": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@role_required(Role.PARENT)
def document_download(request, pk: int):
    update_current_campus_from_request(request)

    doc = get_object_or_404(
        Document.objects.filter(is_active=True).filter(
            Q(audience=Document.ALL) | Q(audience=Document.PARENTS)
        ),
        pk=pk,
    )
    if not doc.file:
        raise Http404("No file")
    return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.file.name.split("/")[-1])
