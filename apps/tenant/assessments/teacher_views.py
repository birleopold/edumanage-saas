from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .forms import AssessmentForm
from .models import Assessment, AssessmentScore
from .services import grade_for_percentage, percentage, score_result, validate_score


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _teacher_profile(request):
    return TeacherProfile.objects.filter(user=request.user).first()


def _teacher_offerings(teacher):
    return CourseOffering.objects.select_related(
        "course",
        "term",
        "term__year",
        "class_group",
    ).filter(teacher=teacher, is_active=True)


@role_required(Role.TEACHER)
def assessment_home(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    offerings = _teacher_offerings(teacher)
    assessments_qs = Assessment.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
    ).filter(offering__in=offerings)

    if q:
        assessments_qs = assessments_qs.filter(
            Q(name__icontains=q)
            | Q(offering__course__name__icontains=q)
            | Q(offering__course__code__icontains=q)
        )

    page_obj = Paginator(assessments_qs, per_page).get_page(page_number)
    assessments = list(page_obj.object_list)
    for assessment in assessments:
        scores = AssessmentScore.objects.filter(assessment=assessment)
        scored = [s for s in scores if s.score is not None]
        assessment.scored_count = len(scored)
        assessment.enrolled_count = Enrollment.objects.filter(offering=assessment.offering, status=Enrollment.ACTIVE).count()
        if scored:
            total_pct = sum((percentage(s.score, assessment.max_score) or 0) for s in scored)
            assessment.average_percentage = total_pct / len(scored)
            assessment.average_grade, assessment.average_remark = grade_for_percentage(assessment.average_percentage)
        else:
            assessment.average_percentage = None
            assessment.average_grade = "-"
            assessment.average_remark = "Not graded"

    return render(
        request,
        "portals/teacher/assessments/home.html",
        {
            "teacher": teacher,
            "assessments": assessments,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@role_required(Role.TEACHER)
def assessment_create(request):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    offerings = _teacher_offerings(teacher)

    if request.method == "POST":
        form = AssessmentForm(request.POST)
        form.fields["offering"].queryset = offerings
        if form.is_valid():
            assessment = form.save(commit=False)
            if assessment.offering_id not in set(offerings.values_list("id", flat=True)):
                return HttpResponseForbidden("You are not allowed to create an assessment for this offering.")
            assessment.save()
            messages.success(request, "Assessment created.")
            return redirect("teacher_assessments_grade", pk=assessment.pk)
    else:
        form = AssessmentForm()
        form.fields["offering"].queryset = offerings

    return render(request, "portals/teacher/assessments/assessment_form.html", {"form": form})


@role_required(Role.TEACHER)
def assessment_grade(request, pk: int):
    teacher = _teacher_profile(request)
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

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

    if assessment.offering.teacher_id != teacher.id:
        return HttpResponseForbidden("You are not allowed to grade this assessment.")

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

    existing_scores = {
        s.student_id: s
        for s in AssessmentScore.objects.filter(assessment=assessment).select_related("student")
    }

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_publish":
            assessment.is_published = not assessment.is_published
            assessment.save(update_fields=["is_published"])
            messages.success(request, "Publish status updated.")
            return redirect("teacher_assessments_grade", pk=assessment.pk)

        student_ids = request.POST.getlist("student_ids")
        updated = 0
        errors = []
        with transaction.atomic():
            for sid in student_ids:
                score_raw = request.POST.get(f"score_{sid}")
                note = request.POST.get(f"note_{sid}") or ""
                value, error = validate_score(score_raw, assessment.max_score)
                if error:
                    errors.append(f"Student #{sid}: {error}")
                    continue

                AssessmentScore.objects.update_or_create(
                    assessment=assessment,
                    student_id=sid,
                    defaults={"score": value, "note": note, "graded_by": teacher},
                )
                updated += 1

        if errors:
            for error in errors[:5]:
                messages.error(request, error)
            if len(errors) > 5:
                messages.error(request, f"{len(errors) - 5} more score error(s) were skipped.")
        if updated:
            messages.success(request, f"Saved scores for {updated} student(s).")
        return redirect(reverse("teacher_assessments_grade", kwargs={"pk": assessment.pk}))

    rows = []
    for enrollment in enrollments_qs:
        score_obj = existing_scores.get(enrollment.student_id)
        rows.append(
            {
                "enrollment": enrollment,
                "student": enrollment.student,
                "score": score_obj,
                "result": score_result(assessment, score_obj),
            }
        )

    scored_count = sum(1 for row in rows if row["result"].score is not None)
    total_count = len(rows)

    return render(
        request,
        "portals/teacher/assessments/grade.html",
        {
            "teacher": teacher,
            "assessment": assessment,
            "rows": rows,
            "enrollments": enrollments_qs,
            "existing_scores": existing_scores,
            "q": q,
            "scored_count": scored_count,
            "total_count": total_count,
            "missing_count": max(total_count - scored_count, 0),
        },
    )
