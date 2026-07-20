from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.academics.models import Level
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required

from .configuration import (
    framework_readiness,
    resolve_effective_terminology,
    sync_framework_stage_links,
)
from .forms import (
    CampusEducationStageForm,
    InstitutionEducationProfileForm,
    LevelStageMappingForm,
    TERMINOLOGY_FIELDS,
    TerminologyOverridesForm,
)
from .models import CampusEducationStage, LevelStageMapping
from .services import (
    enable_mapped_stages,
    ensure_institution_profile,
    ensure_system_templates,
    map_existing_levels,
)


def _profile():
    organization = get_or_create_organization()
    ensure_system_templates()
    return ensure_institution_profile(organization)


@admin_portal_required
def framework_dashboard(request):
    profile = _profile()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        with transaction.atomic():
            if action == "sync_levels":
                summary = map_existing_levels(profile)
                messages.success(
                    request,
                    "Level mapping completed: "
                    f"{summary['created']} created, {summary['updated']} updated and "
                    f"{summary['unchanged']} unchanged. Existing level records were not modified.",
                )
            elif action == "enable_stages":
                created = enable_mapped_stages(profile)
                messages.success(
                    request,
                    f"Campus education stages synchronized. {created} new configuration(s) added.",
                )
            elif action == "sync_framework":
                summary = sync_framework_stage_links(profile)
                messages.success(
                    request,
                    "Framework links synchronized: "
                    f"{summary['updated']} updated, {summary['unchanged']} unchanged and "
                    f"{summary['unsupported']} unsupported stage(s).",
                )
            else:
                messages.warning(request, "No framework setup action was selected.")
        return redirect("admin_education_framework_dashboard")

    mapped_ids = profile.level_mappings.values_list("legacy_level_id", flat=True)
    context = {
        "profile": profile,
        "readiness": framework_readiness(profile),
        "terminology": resolve_effective_terminology(profile=profile),
        "terminology_fields": TERMINOLOGY_FIELDS,
        "campus_stages": profile.campus_stages.select_related(
            "campus",
            "stage",
            "framework_stage",
        ).order_by("campus__name", "stage__order"),
        "level_mappings": profile.level_mappings.select_related("stage").order_by(
            "legacy_level_name"
        ),
        "unmapped_levels": Level.objects.exclude(pk__in=mapped_ids).order_by("order", "name"),
    }
    return render(
        request,
        "portals/admin/education_frameworks/dashboard.html",
        context,
    )


@admin_portal_required
def profile_edit(request):
    profile = _profile()
    previous_framework_id = profile.primary_framework_id
    form = InstitutionEducationProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            profile = form.save()
            if previous_framework_id != profile.primary_framework_id:
                summary = sync_framework_stage_links(profile)
                messages.info(
                    request,
                    "The curriculum framework changed. Existing campus stages were safely relinked: "
                    f"{summary['updated']} updated and {summary['unsupported']} unsupported.",
                )
        messages.success(request, "Institution education profile updated.")
        return redirect("admin_education_framework_dashboard")
    return render(
        request,
        "portals/admin/education_frameworks/form.html",
        {
            "form": form,
            "title": "Institution and Curriculum Profile",
            "description": "Choose the institution type, country, curriculum defaults and terminology mode.",
            "submit_label": "Save Profile",
        },
    )


@admin_portal_required
def terminology_edit(request):
    profile = _profile()
    form = TerminologyOverridesForm(request.POST or None, profile=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Terminology overrides updated. Blank fields continue using framework defaults.")
        return redirect("admin_education_framework_dashboard")
    return render(
        request,
        "portals/admin/education_frameworks/form.html",
        {
            "form": form,
            "title": "Terminology and Localisation",
            "description": "Use simple labels for your market while preserving internationally understandable defaults.",
            "submit_label": "Save Terminology",
        },
    )


@admin_portal_required
def campus_stage_create(request):
    profile = _profile()
    form = CampusEducationStageForm(request.POST or None, profile=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Campus education stage added.")
        return redirect("admin_education_framework_dashboard")
    return render(
        request,
        "portals/admin/education_frameworks/form.html",
        {
            "form": form,
            "title": "Add Campus Education Stage",
            "description": "Enable an education stage for one campus without changing existing classes or levels.",
            "submit_label": "Add Stage",
        },
    )


@admin_portal_required
def campus_stage_edit(request, pk: int):
    profile = _profile()
    campus_stage = get_object_or_404(CampusEducationStage, pk=pk, profile=profile)
    form = CampusEducationStageForm(
        request.POST or None,
        instance=campus_stage,
        profile=profile,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Campus education stage updated.")
        return redirect("admin_education_framework_dashboard")
    return render(
        request,
        "portals/admin/education_frameworks/form.html",
        {
            "form": form,
            "title": "Edit Campus Education Stage",
            "description": "Adjust local labels, academic periods, grading and report settings.",
            "submit_label": "Save Stage",
        },
    )


@admin_portal_required
def mapping_edit(request, pk: int):
    profile = _profile()
    mapping = get_object_or_404(LevelStageMapping, pk=pk, profile=profile)
    form = LevelStageMappingForm(request.POST or None, instance=mapping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            f"Mapping for {mapping.legacy_level_name} updated without changing the original level.",
        )
        return redirect("admin_education_framework_dashboard")
    return render(
        request,
        "portals/admin/education_frameworks/form.html",
        {
            "form": form,
            "title": f"Map Existing Level: {mapping.legacy_level_name}",
            "description": "Correct the education-stage classification while preserving the existing academic level.",
            "submit_label": "Save Mapping",
        },
    )
