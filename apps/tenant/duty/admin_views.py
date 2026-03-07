from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import TeacherDutyRosterForm
from .models import TeacherDutyRoster


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
def roster_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = TeacherDutyRoster.objects.select_related("campus", "teacher").all()
    if q:
        qs = qs.filter(
            Q(teacher__first_name__icontains=q)
            | Q(teacher__last_name__icontains=q)
            | Q(notes__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/duty/list.html",
        {
            "rosters": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "duty_create_url": reverse("admin_duty_create"),
        },
    )


@role_required(Role.ADMIN)
def roster_create(request):
    if request.method == "POST":
        form = TeacherDutyRosterForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Duty roster created.")
            return redirect("admin_duty_list")
    else:
        form = TeacherDutyRosterForm()

    return render(request, "portals/admin/duty/form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def roster_edit(request, pk: int):
    obj = get_object_or_404(TeacherDutyRoster, pk=pk)

    if request.method == "POST":
        form = TeacherDutyRosterForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Duty roster updated.")
            return redirect("admin_duty_list")
    else:
        form = TeacherDutyRosterForm(instance=obj)

    return render(
        request,
        "portals/admin/duty/form.html",
        {"form": form, "mode": "edit", "roster": obj},
    )
