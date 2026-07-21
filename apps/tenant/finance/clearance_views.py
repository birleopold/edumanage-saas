from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .clearance_forms import ClearanceCheckForm, ClearanceOverrideForm, ClearancePolicyForm
from .clearance_models import ClearanceDecisionLog, ClearanceOverride, ClearancePolicy
from .clearance_services import (
    bootstrap_policy_templates,
    clearance_readiness,
    evaluate_clearance,
    record_clearance_decision,
)


@role_required(Role.ADMIN)
def clearance_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "bootstrap":
        rows = bootstrap_policy_templates(apply=True)
        created = sum(1 for row in rows if not row["exists"])
        if created:
            messages.success(request, f"Created {created} inactive clearance-policy template(s).")
        else:
            messages.info(request, "Clearance-policy templates already exist.")
        return redirect("admin_finance_clearance_dashboard")

    policies = ClearancePolicy.objects.select_related(
        "campus", "stage", "level", "program", "academic_term", "academic_term__year"
    )
    overrides = ClearanceOverride.objects.select_related(
        "student", "policy", "academic_term", "approved_by"
    )[:25]
    logs = ClearanceDecisionLog.objects.select_related(
        "student", "policy", "override", "academic_term", "checked_by"
    )[:25]
    return render(
        request,
        "portals/admin/finance/clearance/dashboard.html",
        {
            "readiness": clearance_readiness(),
            "policies": policies,
            "overrides": overrides,
            "decision_logs": logs,
        },
    )


@role_required(Role.ADMIN)
def clearance_policy_create(request):
    if request.method == "POST":
        form = ClearancePolicyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Clearance policy created.")
            return redirect("admin_finance_clearance_dashboard")
    else:
        form = ClearancePolicyForm()
    return render(
        request,
        "portals/admin/finance/clearance/form.html",
        {"form": form, "title": "Add clearance policy"},
    )


@role_required(Role.ADMIN)
def clearance_policy_edit(request, pk: int):
    policy = get_object_or_404(ClearancePolicy, pk=pk)
    if request.method == "POST":
        form = ClearancePolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, "Clearance policy updated.")
            return redirect("admin_finance_clearance_dashboard")
    else:
        form = ClearancePolicyForm(instance=policy)
    return render(
        request,
        "portals/admin/finance/clearance/form.html",
        {"form": form, "title": f"Edit clearance policy — {policy.name}"},
    )


@role_required(Role.ADMIN)
def clearance_override_create(request):
    initial = {}
    student_id = request.GET.get("student")
    if student_id:
        initial["student"] = student_id
    if request.method == "POST":
        form = ClearanceOverrideForm(request.POST)
        if form.is_valid():
            override = form.save(commit=False)
            override.approved_by = request.user
            override.save()
            messages.success(request, "Clearance override approved and recorded.")
            return redirect("admin_finance_clearance_dashboard")
    else:
        form = ClearanceOverrideForm(initial=initial)
    return render(
        request,
        "portals/admin/finance/clearance/form.html",
        {"form": form, "title": "Approve learner clearance override"},
    )


@role_required(Role.ADMIN)
def clearance_override_revoke(request, pk: int):
    override = get_object_or_404(ClearanceOverride, pk=pk)
    if request.method == "POST":
        override.is_active = False
        override.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Clearance override revoked.")
    return redirect("admin_finance_clearance_dashboard")


@role_required(Role.ADMIN)
def clearance_learner_check(request):
    decision = None
    form = ClearanceCheckForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        decision = evaluate_clearance(
            form.cleaned_data["student"],
            form.cleaned_data["access_type"],
            academic_term=form.cleaned_data.get("academic_term"),
        )
        if form.cleaned_data.get("record_decision"):
            record_clearance_decision(
                decision,
                source=ClearanceDecisionLog.ADMIN,
                checked_by=request.user,
            )
            messages.success(request, "Clearance decision recorded for audit.")
    return render(
        request,
        "portals/admin/finance/clearance/learner_check.html",
        {"form": form, "clearance_decision": decision},
    )
