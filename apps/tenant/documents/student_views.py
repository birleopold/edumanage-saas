from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

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


@role_required(Role.STUDENT)
def document_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Document.objects.filter(is_active=True).filter(
        Q(audience=Document.ALL) | Q(audience=Document.STUDENTS)
    )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/student/documents/list.html",
        {"documents": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.STUDENT)
def document_download(request, pk: int):
    doc = get_object_or_404(
        Document.objects.filter(is_active=True).filter(
            Q(audience=Document.ALL) | Q(audience=Document.STUDENTS)
        ),
        pk=pk,
    )
    if not doc.file:
        raise Http404("No file")
    return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.file.name.split("/")[-1])
