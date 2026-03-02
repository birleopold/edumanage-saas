from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .forms import AssessmentForm
from .models import Assessment, AssessmentScore


@role_required(Role.ADMIN)
def assessment_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    qs = Assessment.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
    ).all()

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
            | Q(offering__term__name__icontains=q)
            | Q(offering__term__year__name__icontains=q)
        )

    per_page = 25
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = 25
    per_page = max(1, min(per_page, 200))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/assessments/assessments_list.html",
        {"assessments": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def assessment_create(request):
    if request.method == "POST":
        form = AssessmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_assessments_list")
    else:
        form = AssessmentForm()
    return render(request, "portals/admin/assessments/assessment_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def assessment_edit(request, pk: int):
    obj = get_object_or_404(Assessment, pk=pk)
    if request.method == "POST":
        form = AssessmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("admin_assessments_list")
    else:
        form = AssessmentForm(instance=obj)
    return render(
        request,
        "portals/admin/assessments/assessment_form.html",
        {"form": form, "mode": "edit", "assessment": obj},
    )


@role_required(Role.ADMIN)
def assessment_scores(request, pk: int):
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
            "offering__class_group",
        ),
        pk=pk,
    )
    scores = AssessmentScore.objects.filter(assessment=assessment).select_related("student")
    return render(
        request,
        "portals/admin/assessments/assessment_scores.html",
        {"assessment": assessment, "scores": scores},
    )
