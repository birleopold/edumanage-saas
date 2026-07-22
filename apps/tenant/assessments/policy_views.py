from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from apps.tenant.academics.models import Enrollment
from apps.tenant.portals.permissions import admin_portal_required

from .admin_views import _assessment_queryset_for
from .models import AssessmentScore
from .policy_models import AssessmentPolicy, AssessmentScorePolicy
from .policy_services import (
    assessment_policy_for,
    normalize_score_for_status,
    score_policy_for,
)


@admin_portal_required
def assessment_result_policies(request, pk: int):
    assessment = get_object_or_404(
        _assessment_queryset_for(request.user),
        pk=pk,
    )
    assessment_policy = assessment_policy_for(assessment)
    enrollments = list(
        Enrollment.objects.filter(
            offering=assessment.offering,
            status=Enrollment.ACTIVE,
        )
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )

    if request.method == "POST":
        updated = 0
        errors = []
        allowed_student_ids = {str(item.student_id) for item in enrollments}
        with transaction.atomic():
            for student_id in request.POST.getlist("student_ids"):
                if student_id not in allowed_student_ids:
                    errors.append(f"Student #{student_id}: not enrolled for this assessment.")
                    continue
                score, _ = AssessmentScore.objects.get_or_create(
                    assessment=assessment,
                    student_id=student_id,
                )
                policy = score_policy_for(score)
                attendance_status = request.POST.get(
                    f"attendance_status_{student_id}",
                    AssessmentScorePolicy.PRESENT,
                )
                normalized_score, error = normalize_score_for_status(
                    assessment,
                    score.score,
                    attendance_status,
                )
                if error:
                    errors.append(f"Student #{student_id}: {error}")
                    continue

                score.score = normalized_score
                policy.attendance_status = attendance_status
                policy.competency_rating = request.POST.get(
                    f"competency_rating_{student_id}",
                    AssessmentScorePolicy.NOT_ASSESSED,
                )
                policy.competency_evidence = request.POST.get(
                    f"competency_evidence_{student_id}",
                    "",
                ).strip()
                policy.deferred_until = parse_date(
                    request.POST.get(f"deferred_until_{student_id}", "")
                )
                try:
                    score.full_clean()
                    score.save(update_fields=["score", "graded_at"])
                    policy.full_clean()
                    policy.save()
                except ValidationError as exc:
                    errors.append(
                        f"Student #{student_id}: {'; '.join(exc.messages)}"
                    )
                    continue
                updated += 1

        for error in errors[:8]:
            messages.error(request, error)
        if len(errors) > 8:
            messages.error(
                request,
                f"{len(errors) - 8} additional result-policy error(s) were skipped.",
            )
        if updated:
            messages.success(
                request,
                f"Updated result policies for {updated} learner(s).",
            )
        return redirect("admin_assessment_result_policies", pk=assessment.pk)

    existing_scores = {
        score.student_id: score
        for score in AssessmentScore.objects.filter(
            assessment=assessment,
        ).select_related("student")
    }
    rows = []
    for enrollment in enrollments:
        score = existing_scores.get(enrollment.student_id)
        policy = score_policy_for(score) if score else None
        rows.append(
            {
                "student": enrollment.student,
                "score": score,
                "policy": policy,
            }
        )

    return render(
        request,
        "portals/admin/assessments/result_policies.html",
        {
            "assessment": assessment,
            "assessment_policy": assessment_policy,
            "rows": rows,
            "attendance_choices": AssessmentScorePolicy.STATUS_CHOICES,
            "competency_choices": AssessmentScorePolicy.COMPETENCY_CHOICES,
            "competency_mode": assessment_policy.grading_mode
            in {AssessmentPolicy.COMPETENCY, AssessmentPolicy.MIXED},
        },
    )
