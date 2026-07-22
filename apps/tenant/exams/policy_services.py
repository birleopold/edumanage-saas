from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant.assessments.models import AssessmentType

from .models import ExamPaper, ExamScore
from .policy_models import ExamPaperPolicy, ExamScorePolicy


ZERO = Decimal("0")


def paper_policy_defaults(paper: ExamPaper) -> dict:
    grading_mode = ExamPaperPolicy.NUMERIC
    if (
        paper.assessment_type_id
        and paper.assessment_type.kind == AssessmentType.COMPETENCY
    ):
        grading_mode = ExamPaperPolicy.COMPETENCY
    return {
        "grading_mode": grading_mode,
        "show_on_report": paper.report_cards_enabled,
        "responsible_teacher_id": paper.offering.teacher_id,
    }


def paper_policy_for(paper: ExamPaper) -> ExamPaperPolicy:
    try:
        return paper.policy
    except ExamPaperPolicy.DoesNotExist:
        return ExamPaperPolicy.objects.create(
            paper=paper,
            **paper_policy_defaults(paper),
        )


def score_policy_for(score: ExamScore) -> ExamScorePolicy:
    try:
        return score.policy
    except ExamScorePolicy.DoesNotExist:
        return ExamScorePolicy.objects.create(score_record=score)


def effective_score(paper: ExamPaper, score: ExamScore | None):
    if score is None:
        return None
    policy = score_policy_for(score)
    if policy.makeup_completed_by_id:
        return policy.makeup_completed_by.score
    if policy.attendance_status == ExamScorePolicy.PRESENT:
        return score.score
    paper_policy = paper_policy_for(paper)
    if (
        policy.attendance_status == ExamScorePolicy.ABSENT
        and paper_policy.absence_policy == ExamPaperPolicy.ZERO
    ):
        return ZERO
    return None


def policy_validation_errors(policy) -> list[str]:
    try:
        policy.full_clean()
    except ValidationError as exc:
        return list(exc.messages)
    return []


def exam_policy_readiness() -> dict:
    paper_count = ExamPaper.objects.count()
    score_count = ExamScore.objects.count()
    missing_paper_policies = ExamPaper.objects.filter(policy__isnull=True).count()
    missing_score_policies = ExamScore.objects.filter(policy__isnull=True).count()

    invalid_paper_policies = []
    for policy in ExamPaperPolicy.objects.select_related(
        "paper",
        "paper__offering",
        "paper__offering__class_group",
        "responsible_teacher",
        "makeup_for",
        "makeup_for__offering",
    ):
        errors = policy_validation_errors(policy)
        if errors:
            invalid_paper_policies.append({"policy": policy, "errors": errors})

    invalid_score_policies = []
    for policy in ExamScorePolicy.objects.select_related(
        "score_record",
        "score_record__paper",
        "score_record__student",
        "makeup_completed_by",
        "makeup_completed_by__paper",
    ):
        errors = policy_validation_errors(policy)
        if errors:
            invalid_score_policies.append({"policy": policy, "errors": errors})

    competency_without_rating = ExamScorePolicy.objects.filter(
        score_record__paper__policy__grading_mode=ExamPaperPolicy.COMPETENCY,
        attendance_status=ExamScorePolicy.PRESENT,
        competency_rating=ExamScorePolicy.NOT_ASSESSED,
    ).count()
    report_visibility_mismatch = ExamPaperPolicy.objects.exclude(
        show_on_report=models.F("paper__report_cards_enabled")
    ).count()

    checks = {
        "paper_policies_complete": missing_paper_policies == 0,
        "score_policies_complete": missing_score_policies == 0,
        "paper_policies_valid": not invalid_paper_policies,
        "score_policies_valid": not invalid_score_policies,
        "competency_ratings_complete": competency_without_rating == 0,
        "report_visibility_consistent": report_visibility_mismatch == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "paper_count": paper_count,
        "score_count": score_count,
        "missing_paper_policy_count": missing_paper_policies,
        "missing_score_policy_count": missing_score_policies,
        "invalid_paper_policy_count": len(invalid_paper_policies),
        "invalid_score_policy_count": len(invalid_score_policies),
        "invalid_paper_policies": invalid_paper_policies,
        "invalid_score_policies": invalid_score_policies,
        "competency_without_rating_count": competency_without_rating,
        "report_visibility_mismatch_count": report_visibility_mismatch,
    }
