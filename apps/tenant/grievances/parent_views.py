from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import GrievanceSubmitForm
from .models import Grievance
from .notify import notify_admins_new_grievance


@role_required(Role.PARENT)
def grievance_list(request):
    qs = Grievance.objects.filter(submitted_by=request.user).select_related("campus").order_by(
        "-created_at"
    )
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/parent/grievances/list.html",
        {"page_obj": page_obj},
    )


@role_required(Role.PARENT)
def grievance_detail(request, pk: int):
    grievance = get_object_or_404(
        Grievance.objects.select_related("campus", "handled_by"),
        pk=pk,
        submitted_by=request.user,
    )
    return render(
        request,
        "portals/parent/grievances/detail.html",
        {"grievance": grievance},
    )


@role_required(Role.PARENT)
def grievance_submit(request):
    campus = get_current_campus(request)

    if request.method == "POST":
        form = GrievanceSubmitForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.submitted_by = request.user
            g.campus = campus
            g.save()
            notify_admins_new_grievance(g)
            messages.success(request, "Your concern has been submitted to administration.")
            return redirect("parent_grievances_detail", pk=g.pk)
    else:
        form = GrievanceSubmitForm()

    recent = (
        Grievance.objects.filter(submitted_by=request.user)
        .order_by("-created_at")[:10]
    )
    return render(
        request,
        "portals/parent/grievances/submit.html",
        {"form": form, "recent": recent},
    )
