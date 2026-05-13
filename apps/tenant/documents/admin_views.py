from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .forms import DocumentCreateForm, DocumentEditForm
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


@admin_portal_required
def document_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Document.objects.select_related("uploaded_by").all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/documents/list.html",
        {"documents": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def document_upload(request):
    if request.method == "POST":
        form = DocumentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, "Document uploaded.")
            return redirect("admin_documents_list")
    else:
        form = DocumentCreateForm()

    return render(request, "portals/admin/documents/upload.html", {"form": form})


@admin_portal_required
def document_edit(request, pk: int):
    doc = get_object_or_404(Document, pk=pk)

    if request.method == "POST":
        form = DocumentEditForm(request.POST, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, "Document updated.")
            return redirect("admin_documents_list")
    else:
        form = DocumentEditForm(instance=doc)

    return render(request, "portals/admin/documents/edit.html", {"form": form, "doc": doc})


@admin_portal_required
def document_download(request, pk: int):
    doc = get_object_or_404(Document, pk=pk)
    if not doc.file:
        raise Http404("No file")
    return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.file.name.split("/")[-1])
