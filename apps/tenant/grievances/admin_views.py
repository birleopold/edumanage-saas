from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import admin_portal_required

from .forms import GrievanceAdminForm
from .models import Grievance


@admin_portal_required
def grievance_list(request):
    campus = get_current_campus(request)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    page_number = request.GET.get("page") or 1

    base_qs = Grievance.objects.select_related("submitted_by", "campus", "handled_by").all()
    if campus:
        base_qs = base_qs.filter(Q(campus=campus) | Q(campus__isnull=True))
    if q:
        base_qs = base_qs.filter(Q(subject__icontains=q) | Q(body__icontains=q))

    status_counts_raw = dict(
        base_qs.values("status").annotate(c=Count("id")).values_list("status", "c")
    )
    status_counts_list = [
        {"code": code, "label": label, "count": status_counts_raw.get(code, 0)}
        for code, label in Grievance.STATUS_CHOICES
    ]
    grievance_status_total = sum(row["count"] for row in status_counts_list)

    qs = base_qs
    if status and status in dict(Grievance.STATUS_CHOICES):
        qs = qs.filter(status=status)

    paginator = Paginator(qs.order_by("-created_at"), 25)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/grievances/list.html",
        {
            "page_obj": page_obj,
            "grievances": page_obj.object_list,
            "q": q,
            "status_filter": status,
            "status_choices": Grievance.STATUS_CHOICES,
            "status_counts_list": status_counts_list,
            "grievance_status_total": grievance_status_total,
        },
    )


@admin_portal_required
def grievance_detail(request, pk: int):
    campus = get_current_campus(request)
    grievance = get_object_or_404(
        Grievance.objects.select_related("submitted_by", "campus", "handled_by"),
        pk=pk,
    )
    if campus and grievance.campus_id and grievance.campus_id != campus.id:
        messages.error(request, "This record belongs to another campus.")
        return redirect("admin_grievances_list")

    if request.method == "POST":
        old_status = grievance.status
        form = GrievanceAdminForm(request.POST, instance=grievance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.handled_by = request.user
            obj.save()
            if old_status != obj.status:
                from .notify import notify_grievance_submitter_status_change

                notify_grievance_submitter_status_change(
                    obj, old_status=old_status, actor=request.user
                )
            messages.success(request, "Grievance updated.")
            return redirect("admin_grievances_detail", pk=grievance.pk)
    else:
        form = GrievanceAdminForm(instance=grievance)

    return render(
        request,
        "portals/admin/grievances/detail.html",
        {"grievance": grievance, "form": form},
    )
