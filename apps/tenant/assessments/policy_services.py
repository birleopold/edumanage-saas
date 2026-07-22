from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import Assessment, AssessmentScore, AssessmentType
from .policy_models import AssessmentPolicy, AssessmentScorePolicy


ZERO = Decimal("0")


def assessment_policy_defaults(assessment: Assessment) -> dict:
    grading_mode = AssessmentPolicy.NUMERIC
    if (
        assessment.assessment_type_id
        and assessment.assessment_type.kind == AssessmentType.COMPETENCY
    ):
        grading_mode = AssessmentPolicy.COMPETENCY
    return {
        "grading_mode": grading_mode,
        "responsible_teacher_id": assessment.offering.teacher_id,
    }


def assessment_policy_for(assessment: Assessment) -> AssessmentPolicy:
    try:
        return assessment.policy
    except AssessmentPolicy.DoesNotExist:
        return AssessmentPolicy.objects.create(
            assessment=assessment,
            **assessment_policy_defaults(assessment),
        )


def score_policy_for(score: AssessmentScore) -> AssessmentScorePolicy:
    try:
        return score.policy
    except AssessmentScorePolicy.DoesNotExist:
        return AssessmentScorePolicy.objects.create(score_record=score)


def effective_score(assessment: Assessment, score: AssessmentScore | None):
    if score is None:
        return None
    policy = score_policy_for(score)
    if policy.makeup_completed_by_id:
        return policy.makeup_completed_by.score
    if policy.attendance_status == AssessmentScorePolicy.PRESENT:
        return score.score
    assessment_policy = assessment_policy_for(assessment)
    if (
        policy.attendance_status == AssessmentScorePolicy.ABSENT
        and assessment_policy.absence_policy == AssessmentPolicy.ZERO
    ):
        return ZERO
    return None


def normalize_score_for_status(
    assessment: Assessment,
    score_value,
    attendance_status: str,
):
    policy = assessment_policy_for(assessment)
    if attendance_status == AssessmentScorePolicy.PRESENT:
        return score_value, None
    if attendance_status == AssessmentScorePolicy.ABSENT:
        if policy.absence_policy == AssessmentPolicy.ZERO:
            return ZERO, None
        return None, None
    if attendance_status == AssessmentScorePolicy.EXCUSED:
        return None, None
    if attendance_status in {
        AssessmentScorePolicy.DEFERRED,
        AssessmentScorePolicy.MAKEUP_PENDING,
    }:
        if not policy.allow_makeup:
            return None, "This assessment does not permit deferred or makeup results."
        return None, None
    return score_value, "Choose a valid attendance status."


def result_status(assessment: Assessment, score: AssessmentScore | None) -> str:
    if score is None:
        return "MISSING"
    policy = score_policy_for(score)
    if policy.makeup_completed_by_id:
        return "MAKEUP_COMPLETED"
    return policy.attendance_status


def policy_validation_errors(policy) -> list[str]:
    try:
        policy.full_clean()
    except ValidationError as exc:
        return list(exc.messages)
    return []


def assessment_policy_readiness() -> dict:
    assessment_count = Assessment.objects.count()
    score_count = AssessmentScore.objects.count()
    missing_assessment_policies = Assessment.objects.filter(policy__isnull=True).count()
    missing_score_policies = AssessmentScore.objects.filter(policy__isnull=True).count()

    invalid_assessment_policies = []
    for policy in AssessmentPolicy.objects.select_related(
        "assessment",
        "assessment__offering",
        "assessment__offering__class_group",
        "responsible_teacher",
        "makeup_for",
        "makeup_for__offering",
    ):
        errors = policy_validation_errors(policy)
        if errors:
            invalid_assessment_policies.append({"policy": policy, "errors": errors})

    invalid_score_policies = []
    for policy in AssessmentScorePolicy.objects.select_related(
        "score_record",
        "score_record__assessment",
        "score_record__student",
        "makeup_completed_by",
        "makeup_completed_by__assessment",
    ):
        errors = policy_validation_errors(policy)
        if errors:
            invalid_score_policies.append({"policy": policy, "errors": errors})

    competency_without_rating = AssessmentScorePolicy.objects.filter(
        score_record__assessment__policy__grading_mode=AssessmentPolicy.COMPETENCY,
        attendance_status=AssessmentScorePolicy.PRESENT,
        competency_rating=AssessmentScorePolicy.NOT_ASSESSED,
    ).count()

    checks = {
        "assessment_policies_complete": missing_assessment_policies == 0,
        "score_policies_complete": missing_score_policies == 0,
        "assessment_policies_valid": not invalid_assessment_policies,
        "score_policies_valid": not invalid_score_policies,
        "competency_ratings_complete": competency_without_rating == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "assessment_count": assessment_count,
        "score_count": score_count,
        "missing_assessment_policy_count": missing_assessment_policies,
        "missing_score_policy_count": missing_score_policies,
        "invalid_assessment_policy_count": len(invalid_assessment_policies),
        "invalid_score_policy_count": len(invalid_score_policies),
        "invalid_assessment_policies": invalid_assessment_policies,
        "invalid_score_policies": invalid_score_policies,
        "competency_without_rating_count": competency_without_rating,
        "hidden_from_report_count": AssessmentPolicy.objects.filter(
            show_on_report=False
        ).count(),
    }
