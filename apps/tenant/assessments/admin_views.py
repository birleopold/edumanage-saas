from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required, role_required
from apps.tenant.users.models import Role
from apps.tenant.students.models import StudentProfile

from .comment_suggestions import build_report_comment_suggestion
from .forms import (
    AssessmentForm,
    AssessmentTypeForm,
    AssessmentWeightingComponentForm,
    AssessmentWeightingSchemeForm,
)
from .models import (
    Assessment,
    AssessmentScore,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
)
from .services import (
    assessment_framework_readiness,
    classify_existing_records,
    scheme_validation_errors,
    score_result,
    validate_score,
)


def _offering_queryset_for(user, current_campus=None):
    qs = (
        CourseOffering.objects.filter(is_active=True)
        .select_related("course", "term", "term__year", "class_group", "campus")
        .order_by("-term__year__name", "term__order", "course__name")
    )
    campus = get_user_campus_scope(user) or current_campus
    if campus:
        qs = qs.filter(Q(campus=campus) | Q(campus__isnull=True, class_group__campus=campus)).distinct()
    return qs


def _assessment_queryset_for(user):
    qs = Assessment.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "offering__class_group__campus",
        "offering__campus",
        "assessment_type",
        "weighting_component",
        "weighting_component__scheme",
    )
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(
            Q(offering__campus=scoped)
            | Q(offering__campus__isnull=True, offering__class_group__campus=scoped)
        ).distinct()
    return qs


@admin_portal_required
def assessment_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    qs = _assessment_queryset_for(request.user)

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

    page_obj = Paginator(qs, per_page).get_page(page_number)

    return render(
        request,
        "portals/admin/assessments/assessments_list.html",
        {"assessments": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def assessment_create(request):
    offerings = _offering_queryset_for(request.user)
    if request.method == "POST":
        form = AssessmentForm(request.POST, offerings=offerings)
        if form.is_valid():
            form.save()
            messages.success(request, "Assessment created.")
            return redirect("admin_assessments_list")
    else:
        form = AssessmentForm(offerings=offerings)
    return render(request, "portals/admin/assessments/assessment_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def assessment_edit(request, pk: int):
    offerings = _offering_queryset_for(request.user)
    obj = get_object_or_404(_assessment_queryset_for(request.user), pk=pk)
    if request.method == "POST":
        form = AssessmentForm(request.POST, instance=obj, offerings=offerings)
        if form.is_valid():
            form.save()
            messages.success(request, "Assessment updated.")
            return redirect("admin_assessments_list")
    else:
        form = AssessmentForm(instance=obj, offerings=offerings)
    return render(
        request,
        "portals/admin/assessments/assessment_form.html",
        {"form": form, "mode": "edit", "assessment": obj},
    )


@admin_portal_required
def assessment_scores(request, pk: int):
    assessment = get_object_or_404(
        _assessment_queryset_for(request.user),
        pk=pk,
    )

    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    enrollments_qs = Enrollment.objects.select_related("student").filter(
        offering=assessment.offering,
        status=Enrollment.ACTIVE,
    )
    if q:
        enrollments_qs = enrollments_qs.filter(
            Q(student__student_id__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
        )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_publish":
            assessment.is_published = not assessment.is_published
            assessment.save(update_fields=["is_published"])
            messages.success(request, "Publish status updated.")
            return redirect("admin_assessments_scores", pk=assessment.pk)

        student_ids = request.POST.getlist("student_ids")
        allowed_student_ids = {str(sid) for sid in enrollments_qs.values_list("student_id", flat=True)}
        updated = 0
        errors = []
        with transaction.atomic():
            for sid in student_ids:
                if sid not in allowed_student_ids:
                    errors.append(f"Student #{sid}: not enrolled for this assessment.")
                    continue
                score_raw = request.POST.get(f"score_{sid}")
                note = request.POST.get(f"note_{sid}") or ""
                report_comment = request.POST.get(f"report_comment_{sid}") or ""
                ai_assisted = request.POST.get(f"report_comment_ai_{sid}") == "1"
                value, error = validate_score(score_raw, assessment.max_score)
                if error:
                    errors.append(f"Student #{sid}: {error}")
                    continue
                AssessmentScore.objects.update_or_create(
                    assessment=assessment,
                    student_id=sid,
                    defaults={
                        "score": value,
                        "note": note,
                        "report_comment": report_comment,
                        "report_comment_ai_assisted": ai_assisted and bool(report_comment.strip()),
                    },
                )
                updated += 1
        for error in errors[:5]:
            messages.error(request, error)
        if len(errors) > 5:
            messages.error(request, f"{len(errors) - 5} more score error(s) were skipped.")
        if updated:
            messages.success(request, f"Saved scores for {updated} student(s).")
        return redirect("admin_assessments_scores", pk=assessment.pk)

    existing_scores = {
        s.student_id: s
        for s in AssessmentScore.objects.filter(assessment=assessment).select_related("student")
    }
    rows = []
    for enrollment in enrollments_qs:
        score_obj = existing_scores.get(enrollment.student_id)
        suggestion = build_report_comment_suggestion(assessment, score_obj, enrollment.student)
        rows.append(
            {
                "student": enrollment.student,
                "score": score_obj,
                "result": score_result(assessment, score_obj),
                "comment_suggestion": suggestion,
            }
        )

    scored_count = sum(1 for row in rows if row["result"].score is not None)
    total_count = len(rows)

    return render(
        request,
        "portals/admin/assessments/assessment_scores.html",
        {
            "assessment": assessment,
            "rows": rows,
            "q": q,
            "scored_count": scored_count,
            "total_count": total_count,
            "missing_count": max(total_count - scored_count, 0),
        },
    )


@admin_portal_required
def assessment_tabulation(request):
    """
    Matrix of students (rows) by assessments (columns) for one course offering.
    """
    campus = get_user_campus_scope(request.user) or get_current_campus(request)
    offering_id = request.GET.get("offering")
    print_mode = request.GET.get("print") == "1"

    offerings_qs = _offering_queryset_for(request.user, current_campus=campus)

    if not offering_id:
        return render(
            request,
            "portals/admin/assessments/tabulation_select.html",
            {"offerings": offerings_qs, "campus": campus},
        )

    offering = get_object_or_404(offerings_qs, pk=offering_id)
    assessments = list(Assessment.objects.filter(offering=offering).order_by("date", "id"))

    student_ids = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.ACTIVE).values_list("student_id", flat=True)
    )
    students_qs = StudentProfile.objects.filter(pk__in=student_ids).order_by("last_name", "first_name")
    if not student_ids and offering.class_group_id:
        streams = offering.class_group.streams.filter(is_active=True)
        students_qs = StudentProfile.objects.filter(stream__in=streams, is_active=True).order_by("last_name", "first_name")

    students = list(students_qs)
    score_map = {}
    for sc in AssessmentScore.objects.filter(assessment__offering=offering).select_related("assessment", "student"):
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
    tpl = "portals/admin/assessments/tabulation_print.html" if print_mode else "portals/admin/assessments/tabulation_matrix.html"
    return render(request, tpl, ctx)


@role_required(Role.ADMIN)
def assessment_framework_dashboard(request):
    if request.method == "POST" and request.POST.get("action") == "classify":
        summary = classify_existing_records(dry_run=False, include_exam_papers=True)
        messages.success(
            request,
            "Classification completed: "
            f"{summary['assessments_classified']} assessment(s), "
            f"{summary['exam_papers_classified']} exam paper(s), and "
            f"{summary['assessments_linked'] + summary['exam_papers_linked']} component link(s) added.",
        )
        return redirect("admin_assessment_framework_dashboard")

    readiness = assessment_framework_readiness()
    country_code = ""
    try:
        from apps.tenant.education_frameworks.models import InstitutionEducationProfile

        profile = InstitutionEducationProfile.objects.filter(is_active=True).first()
        country_code = profile.country_code if profile else ""
    except Exception:
        pass
    types = list(AssessmentType.objects.order_by("kind", "name"))
    for item in types:
        item.local_display_name = item.display_name(country_code)
    schemes = AssessmentWeightingScheme.objects.select_related(
        "campus", "stage", "academic_term", "program"
    ).prefetch_related("components__assessment_type")
    scheme_rows = [
        {"scheme": scheme, "errors": scheme_validation_errors(scheme)}
        for scheme in schemes
    ]
    return render(
        request,
        "portals/admin/assessments/framework/dashboard.html",
        {
            "types": types,
            "scheme_rows": scheme_rows,
            "readiness": readiness,
            "country_code": country_code,
        },
    )


@role_required(Role.ADMIN)
def assessment_type_create(request):
    if request.method == "POST":
        form = AssessmentTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Assessment type created.")
            return redirect("admin_assessment_framework_dashboard")
    else:
        form = AssessmentTypeForm()
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {"form": form, "title": "Add assessment type", "back_url_name": "admin_assessment_framework_dashboard"},
    )


@role_required(Role.ADMIN)
def assessment_type_edit(request, pk: int):
    obj = get_object_or_404(AssessmentType, pk=pk)
    if request.method == "POST":
        form = AssessmentTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Assessment type updated.")
            return redirect("admin_assessment_framework_dashboard")
    else:
        form = AssessmentTypeForm(instance=obj)
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {"form": form, "title": "Edit assessment type", "back_url_name": "admin_assessment_framework_dashboard"},
    )


@role_required(Role.ADMIN)
def weighting_scheme_create(request):
    if request.method == "POST":
        form = AssessmentWeightingSchemeForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Weighting scheme created. Add its components next.")
            return redirect("admin_weighting_scheme_detail", pk=obj.pk)
    else:
        form = AssessmentWeightingSchemeForm()
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {"form": form, "title": "Add weighting scheme", "back_url_name": "admin_assessment_framework_dashboard"},
    )


@role_required(Role.ADMIN)
def weighting_scheme_edit(request, pk: int):
    obj = get_object_or_404(AssessmentWeightingScheme, pk=pk)
    if request.method == "POST":
        form = AssessmentWeightingSchemeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Weighting scheme updated.")
            return redirect("admin_weighting_scheme_detail", pk=obj.pk)
    else:
        form = AssessmentWeightingSchemeForm(instance=obj)
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {"form": form, "title": "Edit weighting scheme", "back_url_name": "admin_weighting_scheme_detail", "back_url_pk": obj.pk},
    )


@role_required(Role.ADMIN)
def weighting_scheme_detail(request, pk: int):
    scheme = get_object_or_404(
        AssessmentWeightingScheme.objects.select_related(
            "campus", "stage", "academic_term", "program"
        ).prefetch_related("components__assessment_type"),
        pk=pk,
    )
    components = scheme.components.select_related("assessment_type").order_by("order", "pk")
    return render(
        request,
        "portals/admin/assessments/framework/scheme_detail.html",
        {
            "scheme": scheme,
            "components": components,
            "errors": scheme_validation_errors(scheme),
        },
    )


@role_required(Role.ADMIN)
def weighting_component_create(request, scheme_pk: int):
    scheme = get_object_or_404(AssessmentWeightingScheme, pk=scheme_pk)
    if request.method == "POST":
        form = AssessmentWeightingComponentForm(request.POST, scheme=scheme)
        if form.is_valid():
            form.save()
            messages.success(request, "Weighting component added.")
            return redirect("admin_weighting_scheme_detail", pk=scheme.pk)
    else:
        form = AssessmentWeightingComponentForm(scheme=scheme)
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {"form": form, "title": f"Add component to {scheme.name}", "back_url_name": "admin_weighting_scheme_detail", "back_url_pk": scheme.pk},
    )


@role_required(Role.ADMIN)
def weighting_component_edit(request, pk: int):
    obj = get_object_or_404(AssessmentWeightingComponent.objects.select_related("scheme"), pk=pk)
    if request.method == "POST":
        form = AssessmentWeightingComponentForm(request.POST, instance=obj, scheme=obj.scheme)
        if form.is_valid():
            form.save()
            messages.success(request, "Weighting component updated.")
            return redirect("admin_weighting_scheme_detail", pk=obj.scheme_id)
    else:
        form = AssessmentWeightingComponentForm(instance=obj, scheme=obj.scheme)
    return render(
        request,
        "portals/admin/assessments/framework/form.html",
        {"form": form, "title": "Edit weighting component", "back_url_name": "admin_weighting_scheme_detail", "back_url_pk": obj.scheme_id},
    )
