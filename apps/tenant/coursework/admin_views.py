from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import AssignmentForm, LearningMaterialForm
from .models import Assignment, AssignmentAttachment, LearningMaterial, LearningMaterialAttachment


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.ADMIN)
def material_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = LearningMaterial.objects.select_related("campus", "class_group", "stream", "offering").all()
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


@role_required(Role.ADMIN)
def material_create(request):
    if request.method == "POST":
        form = LearningMaterialForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Material created.")
            return redirect("admin_coursework_materials_list")
    else:
        form = LearningMaterialForm()

    return render(request, "portals/admin/coursework/material_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def material_edit(request, pk: int):
    obj = get_object_or_404(LearningMaterial, pk=pk)

    if request.method == "POST":
        form = LearningMaterialForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Material updated.")
            return redirect("admin_coursework_materials_list")
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


@role_required(Role.ADMIN)
def material_attachment_add(request, pk: int):
    obj = get_object_or_404(LearningMaterial, pk=pk)

    if request.method != "POST":
        return redirect("admin_coursework_materials_edit", pk=obj.pk)

    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Please select at least one file to upload.")
        return redirect("admin_coursework_materials_edit", pk=obj.pk)

    created = 0
    for f in files:
        LearningMaterialAttachment.objects.create(material=obj, file=f)
        created += 1

    messages.success(request, f"Uploaded {created} file(s).")
    return redirect("admin_coursework_materials_edit", pk=obj.pk)


@role_required(Role.ADMIN)
def material_attachment_remove(request, pk: int, attachment_id: int):
    obj = get_object_or_404(LearningMaterial, pk=pk)
    att = get_object_or_404(LearningMaterialAttachment, pk=attachment_id, material=obj)

    # Keep it simple: remove record (and file from storage via FileField delete)
    att.file.delete(save=False)
    att.delete()
    messages.success(request, "Attachment removed.")
    return redirect("admin_coursework_materials_edit", pk=obj.pk)


@role_required(Role.ADMIN)
def assignment_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Assignment.objects.select_related("campus", "class_group", "stream", "offering").all()
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


@role_required(Role.ADMIN)
def assignment_create(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Assignment created.")
            return redirect("admin_coursework_assignments_list")
    else:
        form = AssignmentForm()

    return render(request, "portals/admin/coursework/assignment_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def assignment_edit(request, pk: int):
    obj = get_object_or_404(Assignment, pk=pk)

    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Assignment updated.")
            return redirect("admin_coursework_assignments_list")
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
        },
    )


@role_required(Role.ADMIN)
def assignment_attachment_add(request, pk: int):
    obj = get_object_or_404(Assignment, pk=pk)

    if request.method != "POST":
        return redirect("admin_coursework_assignments_edit", pk=obj.pk)

    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Please select at least one file to upload.")
        return redirect("admin_coursework_assignments_edit", pk=obj.pk)

    created = 0
    for f in files:
        AssignmentAttachment.objects.create(assignment=obj, file=f)
        created += 1

    messages.success(request, f"Uploaded {created} file(s).")
    return redirect("admin_coursework_assignments_edit", pk=obj.pk)


@role_required(Role.ADMIN)
def assignment_attachment_remove(request, pk: int, attachment_id: int):
    obj = get_object_or_404(Assignment, pk=pk)
    att = get_object_or_404(AssignmentAttachment, pk=attachment_id, assignment=obj)

    att.file.delete(save=False)
    att.delete()
    messages.success(request, "Attachment removed.")
    return redirect("admin_coursework_assignments_edit", pk=obj.pk)
