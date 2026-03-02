from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import CampusForm, OrganizationProfileForm
from .models import Campus, FeatureFlag
from .services import DEFAULT_FLAG_CODES, get_feature_flags, get_or_create_organization, set_current_campus


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
def organization_edit(request):
    org = get_or_create_organization()

    if request.method == "POST":
        form = OrganizationProfileForm(request.POST, request.FILES, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization settings saved.")
            return redirect("admin_orgsettings_org")
    else:
        form = OrganizationProfileForm(instance=org)

    return render(request, "portals/admin/orgsettings/org_form.html", {"form": form, "org": org})


@role_required(Role.ADMIN)
def campus_list(request):
    org = get_or_create_organization()

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Campus.objects.filter(organization=org).order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/orgsettings/campuses_list.html",
        {"campuses": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def campus_create(request):
    org = get_or_create_organization()

    if request.method == "POST":
        form = CampusForm(request.POST, request.FILES)
        if form.is_valid():
            campus = form.save(commit=False)
            campus.organization = org
            with transaction.atomic():
                if campus.is_default:
                    Campus.objects.filter(organization=org).update(is_default=False)
                campus.save()
            messages.success(request, "Campus created.")
            return redirect("admin_orgsettings_campuses")
    else:
        form = CampusForm()

    return render(request, "portals/admin/orgsettings/campus_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def campus_edit(request, pk: int):
    org = get_or_create_organization()
    campus = get_object_or_404(Campus, organization=org, pk=pk)

    if request.method == "POST":
        form = CampusForm(request.POST, request.FILES, instance=campus)
        if form.is_valid():
            updated = form.save(commit=False)
            with transaction.atomic():
                if updated.is_default:
                    Campus.objects.filter(organization=org).exclude(pk=campus.pk).update(is_default=False)
                updated.save()
            messages.success(request, "Campus updated.")
            return redirect("admin_orgsettings_campuses")
    else:
        form = CampusForm(instance=campus)

    return render(
        request,
        "portals/admin/orgsettings/campus_form.html",
        {"form": form, "mode": "edit", "campus": campus},
    )


@role_required(Role.ADMIN)
def campus_select(request, pk: int):
    org = get_or_create_organization()
    campus = get_object_or_404(Campus, organization=org, pk=pk, is_active=True)
    set_current_campus(request, campus)

    next_url = request.GET.get("next") or "/admin/"
    messages.success(request, f"Campus set to {campus.name}.")
    return redirect(next_url)


@role_required(Role.ADMIN)
def feature_flags(request):
    org = get_or_create_organization()
    campuses = list(Campus.objects.filter(organization=org).order_by("name"))

    default_codes = DEFAULT_FLAG_CODES

    if request.method == "POST":
        scope = request.POST.get("scope") or "global"
        campus_id = request.POST.get("campus_id")

        campus = None
        if scope == "campus" and campus_id:
            campus = Campus.objects.filter(organization=org, id=campus_id).first()

        for code in default_codes:
            key = f"flag_{code}"
            enabled = key in request.POST
            FeatureFlag.objects.update_or_create(
                code=code,
                campus=campus,
                defaults={"is_enabled": enabled},
            )

        messages.success(request, "Feature flags saved.")
        return redirect("admin_orgsettings_flags")

    global_flags = get_feature_flags(org, None)

    campus_flags = {}
    for c in campuses:
        campus_flags[c.id] = get_feature_flags(org, c)

    return render(
        request,
        "portals/admin/orgsettings/feature_flags.html",
        {"codes": default_codes, "campuses": campuses, "global_flags": global_flags, "campus_flags": campus_flags},
    )
