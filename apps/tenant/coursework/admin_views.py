from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.portals.permissions import admin_portal_required

from .forms import AssignmentForm, LearningMaterialForm
from .models import Assignment, AssignmentAttachment, LearningMaterial, LearningMaterialAttachment
from .services import ensure_assignment_submission_rows, submission_summary_for_assignment


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _add_material_attachments(material: LearningMaterial, files) -> int:
    created = 0
    for uploaded in files or []:
        LearningMaterialAttachment.objects.create(material=material, file=uploaded)
        created += 1
    return created


def _add_assignment_attachments(assignment: Assignment, files) -> int:
    created = 0
    for uploaded in files or []:
        AssignmentAttachment.objects.create(assignment=assignment, file=uploaded)
        created += 1
    return created


@admin_portal_required
def material_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = LearningMaterial.objects.select_related("campus", "class_group", "stream", "offering").prefetch_related("attachments")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/coursework/materials_list.html",
        {
            "materials": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "materials_create_url": reverse("admin_coursework_materials_create"),
        },
    )


@admin_portal_required
def material_create(request):
    if request.method == "POST":
        form = LearningMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            uploaded_count = _add_material_attachments(obj, form.cleaned_data.get("attachments"))
            if uploaded_count:
                messages.success(request, f"Material created with {uploaded_count} attachment(s).")
            else:
                messages.success(request, "Material created.")
            return redirect("admin_coursework_materials_list")
    else:
        form = LearningMaterialForm()

    return render(request, "portals/admin/coursework/material_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def material_edit(request, pk: int):
    obj = get_object_or_404(LearningMaterial.objects.prefetch_related("attachments"), pk=pk)

    if request.method == "POST":
        form = LearningMaterialForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            uploaded_count = _add_material_attachments(obj, form.cleaned_data.get("attachments"))
            if uploaded_count:
                messages.success(request, f"Material updated and {uploaded_count} attachment(s) added.")
            else:
                messages.success(request, "Material updated.")
            return redirect("admin_coursework_materials_edit", pk=obj.pk)
    else:
        form = LearningMaterialForm(instance=obj)

    return render(
        request,
        "portals/admin/coursework/material_form.html",
        {
            "form": form,
            "mode": "edit",
            "material": obj,
            "attachments": obj.attachments.all(),
            "attachments_add_url": reverse("admin_coursework_materials_attachments_add", kwargs={"pk": obj.pk}),
        },
    )


@admin_portal_required
def material_attachment_add(request, pk: int):
    obj = get_object_or_404(LearningMaterial, pk=pk)

    if request.method != "POST":
        return redirect("admin_coursework_materials_edit", pk=obj.pk)

    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Please select at least one file to upload.")
        return redirect("admin_coursework_materials_edit", pk=obj.pk)

    created = _add_material_attachments(obj, files)
    messages.success(request, f"Uploaded {created} file(s).")
    return redirect("admin_coursework_materials_edit", pk=obj.pk)


@admin_portal_required
def material_attachment_remove(request, pk: int, attachment_id: int):
    obj = get_object_or_404(LearningMaterial, pk=pk)
    att = get_object_or_404(LearningMaterialAttachment, pk=attachment_id, material=obj)

    att.file.delete(save=False)
    att.delete()
    messages.success(request, "Attachment removed.")
    return redirect("admin_coursework_materials_edit", pk=obj.pk)


@admin_portal_required
def assignment_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Assignment.objects.select_related("campus", "class_group", "stream", "offering").prefetch_related("attachments")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(instructions__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/coursework/assignments_list.html",
        {
            "assignments": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "assignments_create_url": reverse("admin_coursework_assignments_create"),
        },
    )


@admin_portal_required
def assignment_create(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            uploaded_count = _add_assignment_attachments(obj, form.cleaned_data.get("attachments"))
            created_rows = ensure_assignment_submission_rows(obj)
            extra = []
            if uploaded_count:
                extra.append(f"{uploaded_count} attachment(s)")
            if created_rows:
                extra.append(f"{created_rows} student submission row(s)")
            messages.success(request, "Assignment created" + (" with " + ", ".join(extra) if extra else "") + ".")
            return redirect("admin_coursework_assignments_list")
    else:
        form = AssignmentForm()

    return render(request, "portals/admin/coursework/assignment_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def assignment_edit(request, pk: int):
    obj = get_object_or_404(Assignment.objects.prefetch_related("attachments"), pk=pk)

    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            uploaded_count = _add_assignment_attachments(obj, form.cleaned_data.get("attachments"))
            created_rows = ensure_assignment_submission_rows(obj)
            extra = []
            if uploaded_count:
                extra.append(f"{uploaded_count} attachment(s) added")
            if created_rows:
                extra.append(f"{created_rows} student submission row(s) created")
            messages.success(request, "Assignment updated" + ("; " + "; ".join(extra) if extra else "") + ".")
            return redirect("admin_coursework_assignments_edit", pk=obj.pk)
    else:
        form = AssignmentForm(instance=obj)

    return render(
        request,
        "portals/admin/coursework/assignment_form.html",
        {
            "form": form,
            "mode": "edit",
            "assignment": obj,
            "attachments": obj.attachments.all(),
            "attachments_add_url": reverse("admin_coursework_assignments_attachments_add", kwargs={"pk": obj.pk}),
            "summary": submission_summary_for_assignment(obj),
        },
    )


@admin_portal_required
def assignment_attachment_add(request, pk: int):
    obj = get_object_or_404(Assignment, pk=pk)

    if request.method != "POST":
        return redirect("admin_coursework_assignments_edit", pk=obj.pk)

    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Please select at least one file to upload.")
        return redirect("admin_coursework_assignments_edit", pk=obj.pk)

    created = _add_assignment_attachments(obj, files)
    messages.success(request, f"Uploaded {created} file(s).")
    return redirect("admin_coursework_assignments_edit", pk=obj.pk)


@admin_portal_required
def assignment_attachment_remove(request, pk: int, attachment_id: int):
    obj = get_object_or_404(Assignment, pk=pk)
    att = get_object_or_404(AssignmentAttachment, pk=attachment_id, assignment=obj)

    att.file.delete(save=False)
    att.delete()
    messages.success(request, "Attachment removed.")
    return redirect("admin_coursework_assignments_edit", pk=obj.pk)
