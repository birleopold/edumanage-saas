from __future__ import annotations

import copy
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.academics.models import AcademicTerm
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import roles_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.device_portal import base_template_for
from apps.tenant.users.models import Role

from .field_registry import FIELD_REGISTRY, SAMPLE_VALUES
from .forms import DocumentGenerationForm, DocumentTemplateForm, clean_design_background
from .models import DocumentTemplate, DocumentTemplateVersion, IssuedDocument
from .services import (
    activate_version,
    approve_version,
    default_design,
    get_editable_version,
    issue_document,
    page_dimensions_for,
    render_version_pdf,
    save_draft,
    submit_for_review,
)

ADMIN_ROLES = (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)
APPROVER_ROLES = (Role.ADMIN, Role.PRINCIPAL)


def _can_approve(user) -> bool:
    return bool(user.is_superuser or any(user.has_role(code) for code in APPROVER_ROLES))


def _template_queryset(request):
    qs = DocumentTemplate.objects.select_related("campus", "stage", "level", "created_by")
    campus = get_user_campus_scope(request.user)
    if campus:
        qs = qs.filter(campus=campus)
    return qs


def _student_queryset(request):
    qs = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream__class_group")
    campus = get_user_campus_scope(request.user)
    if campus:
        qs = qs.filter(campus=campus)
    return qs


def _issued_queryset(request):
    qs = IssuedDocument.objects.select_related("template", "version", "student", "academic_term")
    campus = get_user_campus_scope(request.user)
    if campus:
        qs = qs.filter(student__campus=campus)
    return qs


@roles_required(*ADMIN_ROLES)
def dashboard(request):
    templates = list(_template_queryset(request).order_by("document_type", "name"))
    issued = _issued_queryset(request)
    metrics = {
        "templates": len(templates),
        "active": sum(1 for item in templates if item.active_version_number and item.is_active),
        "drafts": DocumentTemplateVersion.objects.filter(template__in=templates, status=DocumentTemplateVersion.DRAFT).count() if templates else 0,
        "issued": issued.count(),
    }
    return render(
        request,
        "portals/designstudio/dashboard.html",
        {
            "base_template": base_template_for(request.user),
            "templates": templates,
            "metrics": metrics,
            "recent_issued": issued.order_by("-issued_at")[:10],
        },
    )


@roles_required(*ADMIN_ROLES)
def template_form(request, pk=None):
    obj = get_object_or_404(_template_queryset(request), pk=pk) if pk else None
    campus = get_user_campus_scope(request.user)
    form = DocumentTemplateForm(request.POST or None, instance=obj, campus=campus)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            template = form.save(commit=False)
            if not template.pk:
                template.created_by = request.user
            template.updated_by = request.user
            template.full_clean()
            template.save()
            if not obj:
                width, height = page_dimensions_for(template.document_type)
                DocumentTemplateVersion.objects.create(
                    template=template,
                    number=1,
                    design=default_design(template.document_type),
                    page_width_mm=width,
                    page_height_mm=height,
                    created_by=request.user,
                )
        messages.success(request, "Document template saved. Open the designer to arrange its layout.")
        return redirect("designstudio:editor", pk=template.pk)
    return render(
        request,
        "portals/designstudio/template_form.html",
        {"base_template": base_template_for(request.user), "form": form, "object": obj},
    )


@require_POST
@roles_required(*ADMIN_ROLES)
def template_duplicate(request, pk):
    source = get_object_or_404(_template_queryset(request), pk=pk)
    source_version = source.latest_version
    with transaction.atomic():
        clone = DocumentTemplate.objects.create(
            name=f"{source.name} — Copy",
            document_type=source.document_type,
            description=source.description,
            campus=source.campus,
            stage=source.stage,
            level=source.level,
            is_default=False,
            is_active=True,
            created_by=request.user,
            updated_by=request.user,
        )
        if source_version:
            version = DocumentTemplateVersion(
                template=clone,
                number=1,
                design=copy.deepcopy(source_version.design),
                page_width_mm=source_version.page_width_mm,
                page_height_mm=source_version.page_height_mm,
                background_fit=source_version.background_fit,
                created_by=request.user,
            )
            if source_version.background:
                version.background.name = source_version.background.name
            version.save()
        else:
            width, height = page_dimensions_for(clone.document_type)
            DocumentTemplateVersion.objects.create(
                template=clone,
                number=1,
                design=default_design(clone.document_type),
                page_width_mm=width,
                page_height_mm=height,
                created_by=request.user,
            )
    messages.success(request, "Template duplicated as a new editable draft.")
    return redirect("designstudio:editor", pk=clone.pk)


@roles_required(*ADMIN_ROLES)
def editor(request, pk):
    template = get_object_or_404(_template_queryset(request), pk=pk)
    version = template.latest_version or get_editable_version(template, request.user)
    is_editable = version.status == DocumentTemplateVersion.DRAFT
    if request.method == "POST":
        posted_version = get_object_or_404(DocumentTemplateVersion, pk=request.POST.get("version_id"), template=template)
        if posted_version.status != DocumentTemplateVersion.DRAFT:
            messages.error(request, "Official and submitted versions are immutable. Start a new revision to make changes.")
            return redirect("designstudio:editor", pk=template.pk)
        try:
            design = json.loads(request.POST.get("design_json") or "{}")
            width = float(request.POST.get("page_width_mm") or posted_version.page_width_mm)
            height = float(request.POST.get("page_height_mm") or posted_version.page_height_mm)
            background = clean_design_background(request.FILES.get("background")) if "background" in request.FILES else None
            save_draft(
                posted_version,
                design=design,
                width=width,
                height=height,
                background=background,
                background_fit=request.POST.get("background_fit") or posted_version.background_fit,
                notes=request.POST.get("notes", ""),
            )
            template.updated_by = request.user
            template.save(update_fields=["updated_by", "updated_at"])
            messages.success(request, f"Design v{posted_version.number} saved.")
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("designstudio:editor", pk=template.pk)

    students = _student_queryset(request).order_by("last_name", "first_name")[:500]
    terms = AcademicTerm.objects.select_related("year").order_by("-year__name", "order")[:30]
    return render(
        request,
        "portals/designstudio/editor.html",
        {
            "base_template": base_template_for(request.user),
            "template": template,
            "version": version,
            "design": version.design,
            "field_registry": FIELD_REGISTRY,
            "sample_values": SAMPLE_VALUES,
            "students": students,
            "terms": terms,
            "can_approve": _can_approve(request.user),
            "is_editable": is_editable,
        },
    )


@roles_required(*ADMIN_ROLES)
def preview_pdf(request, pk):
    template = get_object_or_404(_template_queryset(request), pk=pk)
    version_id = request.GET.get("version")
    version = get_object_or_404(DocumentTemplateVersion, pk=version_id, template=template) if version_id else template.latest_version
    if not version:
        raise Http404("This template has no design version.")
    student_id = request.GET.get("student")
    student = get_object_or_404(_student_queryset(request), pk=student_id) if student_id else _student_queryset(request).first()
    if not student:
        raise Http404("Create a learner record before previewing a data-bound document.")
    term = get_object_or_404(AcademicTerm, pk=request.GET.get("term")) if request.GET.get("term") else None
    pdf = render_version_pdf(
        version,
        student,
        term,
        verification_url=request.build_absolute_uri("/design-studio/verify/PREVIEW/"),
    )
    response = FileResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{template.name}-preview.pdf"'
    response["Cache-Control"] = "no-store"
    return response


@roles_required(*ADMIN_ROLES)
def generate_document(request, pk):
    template = get_object_or_404(_template_queryset(request), pk=pk)
    campus = get_user_campus_scope(request.user)
    form = DocumentGenerationForm(request.POST or None, request.FILES or None, campus=campus, template=template)
    if request.method == "POST" and form.is_valid():
        if not template.active_version:
            messages.error(request, "Approve and activate a design version before issuing an official document.")
        else:
            student = form.cleaned_data["student"]
            portrait = form.cleaned_data.get("student_photo")
            if portrait:
                student.photo = portrait
                student.save(update_fields=["photo"])
            term = form.cleaned_data.get("academic_term")
            issued = issue_document(
                template,
                student,
                term,
                request.user,
                lambda token: request.build_absolute_uri(reverse("designstudio:verify", args=[token])),
            )
            messages.success(request, f"Official document {issued.reference} issued and locked to design v{issued.version.number}.")
            return redirect("designstudio:issued_download", pk=issued.pk)
    return render(
        request,
        "portals/designstudio/generate.html",
        {"base_template": base_template_for(request.user), "template": template, "form": form},
    )


@require_POST
@roles_required(*ADMIN_ROLES)
def version_action(request, pk, action):
    version = get_object_or_404(DocumentTemplateVersion.objects.select_related("template"), pk=pk)
    if not _template_queryset(request).filter(pk=version.template_id).exists():
        return HttpResponseForbidden("This template belongs to another campus.")
    try:
        if action == "submit":
            submit_for_review(version, request.user)
            message = "Design submitted for approval. It is now read-only until approved or revised."
        elif action == "approve":
            if not _can_approve(request.user):
                return HttpResponseForbidden("Only a school administrator or principal can approve official document designs.")
            approve_version(version, request.user)
            message = "Design approved."
        elif action == "activate":
            if not _can_approve(request.user):
                return HttpResponseForbidden("Only a school administrator or principal can activate official document designs.")
            activate_version(version, request.user)
            message = f"Design v{version.number} is now active. Previous active versions were archived."
        elif action == "revise":
            if version.status not in {DocumentTemplateVersion.APPROVED, DocumentTemplateVersion.ACTIVE, DocumentTemplateVersion.ARCHIVED}:
                raise ValidationError("Only an official version can be copied into a new revision.")
            draft = get_editable_version(version.template, request.user)
            message = f"Draft v{draft.number} created from v{version.number}."
        else:
            raise Http404
        messages.success(request, message)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("designstudio:editor", pk=version.template_id)


@roles_required(*ADMIN_ROLES)
def issued_download(request, pk):
    issued = get_object_or_404(_issued_queryset(request), pk=pk)
    if not issued.pdf_file:
        raise Http404("The issued PDF is unavailable.")
    issued.pdf_file.open("rb")
    response = FileResponse(issued.pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{issued.reference}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
@roles_required(*ADMIN_ROLES)
def issued_revoke(request, pk):
    issued = get_object_or_404(_issued_queryset(request), pk=pk)
    if issued.status == IssuedDocument.ACTIVE:
        issued.status = IssuedDocument.REVOKED
        issued.revoked_by = request.user
        issued.revoked_at = timezone.now()
        issued.revocation_reason = request.POST.get("reason", "").strip()
        issued.save(update_fields=["status", "revoked_by", "revoked_at", "revocation_reason"])
        messages.success(request, f"{issued.reference} has been revoked. Its verification page now shows it as invalid.")
    return redirect("designstudio:dashboard")


def verify_document(request, token):
    if token == "PREVIEW":
        return render(request, "portals/designstudio/verify.html", {"preview": True, "document": None})
    document = IssuedDocument.objects.select_related("template", "version", "student", "academic_term").filter(verification_token=token).first()
    return render(request, "portals/designstudio/verify.html", {"document": document, "preview": False})
