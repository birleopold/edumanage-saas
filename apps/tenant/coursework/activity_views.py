from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .activity_forms import LearningActivityPolicyForm
from .activity_services import learning_activity_readiness, sync_all_learning_activities
from .models import LearningActivity


@role_required(Role.ADMIN)
def activity_framework_dashboard(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"sync", "refresh"}:
            summary = sync_all_learning_activities(refresh_policy=action == "refresh")
            messages.success(
                request,
                "Learning activities synchronized: "
                f"{summary['materials_created']} material link(s), "
                f"{summary['assignments_created']} assignment link(s), "
                f"{summary['activities_updated']} activity update(s), and "
                f"{summary['metadata_links_added']} compatibility link(s).",
            )
            return redirect("admin_coursework_activity_framework")

    q = (request.GET.get("q") or "").strip()
    kind = (request.GET.get("kind") or "").strip()
    qs = LearningActivity.objects.select_related(
        "material",
        "assignment",
        "assessment_type",
        "weighting_component",
        "weighting_component__scheme",
    )
    if q:
        qs = qs.filter(title_snapshot__icontains=q)
    if kind:
        qs = qs.filter(kind=kind)
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "portals/admin/coursework/activity_framework.html",
        {
            "activities": page_obj.object_list,
            "page_obj": page_obj,
            "readiness": learning_activity_readiness(),
            "kind_choices": LearningActivity.KIND_CHOICES,
            "selected_kind": kind,
            "q": q,
        },
    )


@role_required(Role.ADMIN)
def activity_policy_edit(request, pk: int):
    activity = get_object_or_404(
        LearningActivity.objects.select_related("material", "assignment", "assessment_type", "weighting_component"),
        pk=pk,
    )
    if request.method == "POST":
        form = LearningActivityPolicyForm(request.POST, instance=activity)
        if form.is_valid():
            form.save()
            messages.success(request, "Learning activity policy updated.")
            return redirect("admin_coursework_activity_framework")
    else:
        form = LearningActivityPolicyForm(instance=activity)
    return render(
        request,
        "portals/admin/coursework/activity_policy_form.html",
        {"form": form, "activity": activity},
    )
