from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .grading_forms import GradingProfileForm, ReportRuleForm
from .grading_services import (
    bootstrap_default_grading_profile,
    grading_framework_readiness,
    grading_profile_errors,
)
from .models import GradingProfile, ReportRule


@role_required(Role.ADMIN)
def grading_framework_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "bootstrap":
        summary = bootstrap_default_grading_profile(dry_run=False)
        if summary["profile_created"]:
            messages.success(request, "Default grading profile and report rules created.")
        elif summary["profile_existing"]:
            messages.success(request, "Default grading profile already exists; missing report rules were repaired.")
        else:
            messages.warning(
                request,
                "No valid active default grading scale is available. Configure its grade ranges first.",
            )
        return redirect("admin_grading_framework_dashboard")

    readiness = grading_framework_readiness()
    profiles = GradingProfile.objects.select_related(
        "grading_scale", "campus", "stage", "level", "program", "academic_term"
    ).prefetch_related("grading_scale__ranges")
    rows = [{"profile": profile, "errors": grading_profile_errors(profile)} for profile in profiles]
    return render(
        request,
        "portals/admin/assessments/grading/dashboard.html",
        {"readiness": readiness, "profile_rows": rows},
    )


@role_required(Role.ADMIN)
def grading_profile_create(request):
    if request.method == "POST":
        form = GradingProfileForm(request.POST)
        if form.is_valid():
            profile = form.save()
            ReportRule.objects.get_or_create(grading_profile=profile)
            messages.success(request, "Grading profile created with default report rules.")
            return redirect("admin_grading_framework_dashboard")
    else:
        form = GradingProfileForm()
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {
            "form": form,
            "title": "Add grading profile",
            "back_url_name": "admin_grading_framework_dashboard",
        },
    )


@role_required(Role.ADMIN)
def grading_profile_edit(request, pk: int):
    profile = get_object_or_404(GradingProfile, pk=pk)
    if request.method == "POST":
        form = GradingProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Grading profile updated.")
            return redirect("admin_grading_framework_dashboard")
    else:
        form = GradingProfileForm(instance=profile)
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {
            "form": form,
            "title": "Edit grading profile",
            "back_url_name": "admin_grading_framework_dashboard",
        },
    )


@role_required(Role.ADMIN)
def report_rule_edit(request, profile_pk: int):
    profile = get_object_or_404(GradingProfile, pk=profile_pk)
    rule, _ = ReportRule.objects.get_or_create(grading_profile=profile)
    if request.method == "POST":
        form = ReportRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, "Report-card rules updated.")
            return redirect("admin_grading_framework_dashboard")
    else:
        form = ReportRuleForm(instance=rule)
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {
            "form": form,
            "title": f"Report rules — {profile.name}",
            "back_url_name": "admin_grading_framework_dashboard",
        },
    )
