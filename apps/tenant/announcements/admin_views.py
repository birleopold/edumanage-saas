from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import AnnouncementForm
from .models import Announcement


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
def announcement_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Announcement.objects.all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/announcements/list.html",
        {"announcements": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def announcement_create(request):
    if request.method == "POST":
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement created.")
            return redirect("admin_announcements_list")
    else:
        form = AnnouncementForm()

    return render(request, "portals/admin/announcements/form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def announcement_edit(request, pk: int):
    obj = get_object_or_404(Announcement, pk=pk)

    if request.method == "POST":
        form = AnnouncementForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement updated.")
            return redirect("admin_announcements_list")
    else:
        form = AnnouncementForm(instance=obj)

    return render(
        request,
        "portals/admin/announcements/form.html",
        {"form": form, "mode": "edit", "announcement": obj},
    )
