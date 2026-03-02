from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

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


@role_required(Role.ADMIN)
def incident_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Incident.objects.select_related("student", "reported_by").all()

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


@role_required(Role.ADMIN)
def incident_create(request):
    if request.method == "POST":
        form = IncidentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Incident created.")
            return redirect("admin_incidents_list")
    else:
        form = IncidentForm()

    return render(
        request,
        "portals/admin/discipline/incident_form.html",
        {"form": form, "mode": "create"},
    )


@role_required(Role.ADMIN)
def incident_edit(request, pk: int):
    incident = get_object_or_404(Incident, pk=pk)

    if request.method == "POST":
        form = IncidentForm(request.POST, instance=incident)
        if form.is_valid():
            form.save()
            messages.success(request, "Incident updated.")
            return redirect("admin_incidents_detail", pk=incident.pk)
    else:
        form = IncidentForm(instance=incident)

    return render(
        request,
        "portals/admin/discipline/incident_form.html",
        {"form": form, "mode": "edit", "incident": incident},
    )


@role_required(Role.ADMIN)
def incident_detail(request, pk: int):
    incident = get_object_or_404(
        Incident.objects.select_related("student", "reported_by").prefetch_related("actions"),
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
