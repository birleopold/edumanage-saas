from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode

from .models import Domain, Tenant
from .onboarding import provision_school_tenant
from .platform_views import platform_admin_required
from .wizard_forms import (
    ConfirmActivationStepForm,
    DomainDetailsStepForm,
    FEATURE_LABELS,
    FEATURE_PACKAGES,
    OwnerAdminStepForm,
    PackageFeaturesStepForm,
    SchoolDetailsStepForm,
)


WIZARD_SESSION_KEY = "platform_create_school_wizard"
WIZARD_STEPS = (
    {"key": "school", "title": "School details", "icon": "ph-buildings"},
    {"key": "domain", "title": "Domain details", "icon": "ph-globe"},
    {"key": "owner", "title": "Owner/admin account", "icon": "ph-user-circle-gear"},
    {"key": "features", "title": "Package/features", "icon": "ph-squares-four"},
    {"key": "confirm", "title": "Confirm and activate", "icon": "ph-rocket-launch"},
)
STEP_ORDER = tuple(step["key"] for step in WIZARD_STEPS)
FORM_CLASSES = {
    "school": SchoolDetailsStepForm,
    "domain": DomainDetailsStepForm,
    "owner": OwnerAdminStepForm,
    "features": PackageFeaturesStepForm,
    "confirm": ConfirmActivationStepForm,
}


def _wizard_url(step: str) -> str:
    return f"{reverse('platform_tenant_create')}?{urlencode({'step': step})}"


def _get_wizard_data(request) -> dict:
    return request.session.get(WIZARD_SESSION_KEY, {})


def _set_wizard_data(request, data: dict):
    request.session[WIZARD_SESSION_KEY] = data
    request.session.modified = True


def _clear_wizard_data(request):
    request.session.pop(WIZARD_SESSION_KEY, None)
    request.session.modified = True


def _previous_step(step: str) -> str | None:
    index = STEP_ORDER.index(step)
    return STEP_ORDER[index - 1] if index > 0 else None


def _next_step(step: str) -> str | None:
    index = STEP_ORDER.index(step)
    return STEP_ORDER[index + 1] if index + 1 < len(STEP_ORDER) else None


def _first_missing_step(data: dict, requested_step: str) -> str | None:
    for step in STEP_ORDER:
        if step == requested_step:
            return None
        if step != "confirm" and step not in data:
            return step
    return None


def _cleaned_for_session(cleaned_data: dict) -> dict:
    session_data = {}
    for key, value in cleaned_data.items():
        if isinstance(value, tuple):
            value = list(value)
        session_data[key] = value
    return session_data


def _form_for_step(step: str, *, data=None, initial=None, wizard_data=None):
    wizard_data = wizard_data or {}
    form_class = FORM_CLASSES[step]
    if step == "owner":
        schema_name = (wizard_data.get("school") or {}).get("schema_name")
        return form_class(data=data, initial=initial, schema_name=schema_name)
    return form_class(data=data, initial=initial)


def _wizard_summary(wizard_data: dict) -> dict:
    school = wizard_data.get("school", {})
    domain = wizard_data.get("domain", {})
    owner = wizard_data.get("owner", {})
    features = wizard_data.get("features", {})
    selected_codes = features.get("feature_flags") or []
    package_code = features.get("package") or "standard"
    package_label = FEATURE_PACKAGES.get(package_code, {}).get("label", package_code.title())
    return {
        "school": school,
        "domain": domain,
        "owner": owner,
        "package_label": package_label,
        "selected_features": [(code, FEATURE_LABELS.get(code, code.replace("_", " ").title())) for code in selected_codes],
    }


def _validate_all_steps(wizard_data: dict):
    school_form = SchoolDetailsStepForm(data=wizard_data.get("school") or {})
    domain_form = DomainDetailsStepForm(data=wizard_data.get("domain") or {})
    owner_form = OwnerAdminStepForm(data=wizard_data.get("owner") or {}, schema_name=(wizard_data.get("school") or {}).get("schema_name"))
    features_form = PackageFeaturesStepForm(data=wizard_data.get("features") or {})
    forms = {
        "school": school_form,
        "domain": domain_form,
        "owner": owner_form,
        "features": features_form,
    }
    is_valid = all(form.is_valid() for form in forms.values())
    return is_valid, forms


@platform_admin_required
def create_school_wizard(request):
    requested_step = request.GET.get("step") or request.POST.get("step") or "school"
    step = requested_step if requested_step in STEP_ORDER else "school"
    wizard_data = _get_wizard_data(request)

    if request.method == "POST" and request.POST.get("action") == "reset":
        _clear_wizard_data(request)
        messages.info(request, "Create School Wizard has been reset.")
        return redirect(_wizard_url("school"))

    missing_step = _first_missing_step(wizard_data, step)
    if missing_step is not None:
        messages.info(request, "Complete the earlier wizard step before continuing.")
        return redirect(_wizard_url(missing_step))

    if request.method == "POST" and request.POST.get("action") == "back":
        previous_step = _previous_step(step) or "school"
        return redirect(_wizard_url(previous_step))

    if request.method == "POST":
        form = _form_for_step(step, data=request.POST, wizard_data=wizard_data)
        if form.is_valid():
            if step == "confirm":
                is_valid, forms = _validate_all_steps(wizard_data)
                if not is_valid:
                    for broken_step, broken_form in forms.items():
                        if broken_form.errors:
                            messages.error(request, f"Please review the {broken_step} step before activation.")
                            return redirect(_wizard_url(broken_step))
                with transaction.atomic():
                    school = forms["school"].cleaned_data
                    domain_data = forms["domain"].cleaned_data
                    owner = forms["owner"].cleaned_data
                    features = forms["features"].cleaned_data
                    tenant = Tenant.objects.create(
                        name=school["name"],
                        schema_name=school["schema_name"],
                        status=school["status"],
                    )
                    domain = Domain.objects.create(
                        tenant=tenant,
                        domain=domain_data["domain"],
                        type=domain_data["domain_type"],
                        is_primary=True,
                    )
                    onboarding = provision_school_tenant(
                        tenant=tenant,
                        domain=domain,
                        organization_email=school.get("organization_email", ""),
                        organization_phone=school.get("organization_phone", ""),
                        organization_address=school.get("organization_address", ""),
                        owner_first_name=owner.get("owner_first_name", ""),
                        owner_last_name=owner.get("owner_last_name", ""),
                        owner_email=owner["owner_email"],
                        owner_username=owner["owner_username"],
                        enabled_feature_codes=features["feature_flags"],
                    )
                _clear_wizard_data(request)
                messages.success(request, f"{tenant.name} has been activated with tenant, domain, organization profile, campus, admin user, features and academic period.")
                messages.info(request, f"School admin username: {onboarding.admin_user.username}. Login domain: {onboarding.login_domain}.")
                return redirect("platform_tenant_detail", pk=tenant.pk)

            wizard_data[step] = _cleaned_for_session(form.cleaned_data)
            _set_wizard_data(request, wizard_data)
            return redirect(_wizard_url(_next_step(step) or "confirm"))
    else:
        form = _form_for_step(step, initial=wizard_data.get(step), wizard_data=wizard_data)

    context = {
        "form": form,
        "steps": WIZARD_STEPS,
        "step": step,
        "step_index": STEP_ORDER.index(step) + 1,
        "step_count": len(STEP_ORDER),
        "previous_step": _previous_step(step),
        "next_step": _next_step(step),
        "summary": _wizard_summary(wizard_data),
        "is_confirm_step": step == "confirm",
    }
    return render(request, "platform/create_school_wizard.html", context)
