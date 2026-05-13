from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .forms import AssessmentForm
from .models import Assessment, AssessmentScore


@admin_portal_required
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


@admin_portal_required
def assessment_create(request):
    if request.method == "POST":
        form = AssessmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_assessments_list")
    else:
        form = AssessmentForm()
    return render(request, "portals/admin/assessments/assessment_form.html", {"form": form, "mode": "create"})


@admin_portal_required
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


@admin_portal_required
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


@admin_portal_required
def assessment_tabulation(request):
    """
    Matrix of students (rows) by assessments (columns) for one course offering.
    """
    campus = get_current_campus(request)
    offering_id = request.GET.get("offering")
    print_mode = request.GET.get("print") == "1"

    offerings_qs = (
        CourseOffering.objects.filter(is_active=True)
        .select_related("course", "term", "term__year", "class_group", "campus")
        .order_by("-term__year__name", "term__order", "course__name")
    )
    if campus:
        offerings_qs = (
            offerings_qs.filter(
                Q(campus=campus)
                | Q(campus__isnull=True, class_group__campus=campus)
            )
            .distinct()
        )

    if not offering_id:
        return render(
            request,
            "portals/admin/assessments/tabulation_select.html",
            {"offerings": offerings_qs, "campus": campus},
        )

    offering = get_object_or_404(offerings_qs, pk=offering_id)
    assessments = list(
        Assessment.objects.filter(offering=offering).order_by("date", "id")
    )

    student_ids = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.ACTIVE).values_list(
            "student_id", flat=True
        )
    )
    students_qs = StudentProfile.objects.filter(pk__in=student_ids).order_by(
        "last_name", "first_name"
    )
    if not student_ids and offering.class_group_id:
        streams = offering.class_group.streams.filter(is_active=True)
        students_qs = StudentProfile.objects.filter(
            stream__in=streams, is_active=True
        ).order_by("last_name", "first_name")

    students = list(students_qs)
    score_map = {}
    for sc in AssessmentScore.objects.filter(assessment__offering=offering).select_related(
        "assessment", "student"
    ):
        score_map[(sc.student_id, sc.assessment_id)] = sc.score

    rows = []
    for st in students:
        cells = [score_map.get((st.pk, a.pk)) for a in assessments]
        rows.append({"student": st, "cells": cells})

    ctx = {
        "offering": offering,
        "assessments": assessments,
        "rows": rows,
        "campus": campus,
    }
    tpl = (
        "portals/admin/assessments/tabulation_print.html"
        if print_mode
        else "portals/admin/assessments/tabulation_matrix.html"
    )
    return render(request, tpl, ctx)
