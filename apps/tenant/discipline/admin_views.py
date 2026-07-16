from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .forms import IncidentActionForm, IncidentForm
from .models import Incident, IncidentAction


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _incident_queryset_for(user):
    qs = Incident.objects.select_related("student", "student__campus", "reported_by")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(student__campus=scoped)
    return qs


@admin_portal_required
def incident_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _incident_queryset_for(request.user)

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(category__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/discipline/incidents_list.html",
        {"incidents": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def incident_create(request):
    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = IncidentForm(request.POST, campus_scope=scoped)
        if form.is_valid():
            form.save()
            messages.success(request, "Incident created.")
            return redirect("admin_incidents_list")
    else:
        form = IncidentForm(campus_scope=scoped)

    return render(
        request,
        "portals/admin/discipline/incident_form.html",
        {"form": form, "mode": "create"},
    )


@admin_portal_required
def incident_edit(request, pk: int):
    scoped = get_user_campus_scope(request.user)
    incident = get_object_or_404(_incident_queryset_for(request.user), pk=pk)

    if request.method == "POST":
        form = IncidentForm(request.POST, instance=incident, campus_scope=scoped)
        if form.is_valid():
            form.save()
            messages.success(request, "Incident updated.")
            return redirect("admin_incidents_detail", pk=incident.pk)
    else:
        form = IncidentForm(instance=incident, campus_scope=scoped)

    return render(
        request,
        "portals/admin/discipline/incident_form.html",
        {"form": form, "mode": "edit", "incident": incident},
    )


@admin_portal_required
def incident_detail(request, pk: int):
    incident = get_object_or_404(
        _incident_queryset_for(request.user).prefetch_related("actions"),
        pk=pk,
    )

    action_form = IncidentActionForm()

    if request.method == "POST":
        action_form = IncidentActionForm(request.POST)
        if action_form.is_valid():
            with transaction.atomic():
                action = action_form.save(commit=False)
                action.incident = incident
                action.performed_by_user = request.user
                action.save()
            messages.success(request, "Action added.")
            return redirect("admin_incidents_detail", pk=incident.pk)

    actions = IncidentAction.objects.filter(incident=incident)

    return render(
        request,
        "portals/admin/discipline/incident_detail.html",
        {
            "incident": incident,
            "actions": actions,
            "action_form": action_form,
        },
    )
