from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

from django.db.models import QuerySet

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile

from .models import Assessment, AssessmentScore


@dataclass(frozen=True)
class GradeBand:
    min_percentage: Decimal
    letter: str
    remark: str


DEFAULT_GRADE_BANDS = (
    GradeBand(Decimal("80"), "A", "Excellent"),
    GradeBand(Decimal("70"), "B", "Very good"),
    GradeBand(Decimal("60"), "C", "Good"),
    GradeBand(Decimal("50"), "D", "Fair"),
    GradeBand(Decimal("0"), "F", "Needs improvement"),
)


@dataclass(frozen=True)
class ScoreResult:
    score: Decimal | None
    max_score: Decimal
    percentage: Decimal | None
    grade: str
    remark: str
    note: str
    report_comment: str
    report_comment_ai_assisted: bool
    is_missing: bool


@dataclass(frozen=True)
class CourseResult:
    offering: CourseOffering
    assessments: list[dict]
    total_weight: Decimal
    weighted_percentage: Decimal | None
    simple_percentage: Decimal | None
    grade: str
    remark: str
    completed_count: int
    assessment_count: int


@dataclass(frozen=True)
class ReportCard:
    student: StudentProfile
    course_results: list[CourseResult]
    overall_percentage: Decimal | None
    overall_grade: str
    overall_remark: str
    published_assessment_count: int
    completed_assessment_count: int


def _to_decimal(value, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def quantize_percent(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percentage(score: Decimal | None, max_score: Decimal | None) -> Decimal | None:
    score_dec = _to_decimal(score)
    max_dec = _to_decimal(max_score)
    if score_dec is None or max_dec is None or max_dec <= 0:
        return None
    return quantize_percent((score_dec / max_dec) * Decimal("100"))


def grade_for_percentage(value: Decimal | None, bands: Iterable[GradeBand] = DEFAULT_GRADE_BANDS) -> tuple[str, str]:
    if value is None:
        return "-", "Not graded"
    for band in sorted(bands, key=lambda b: b.min_percentage, reverse=True):
        if value >= band.min_percentage:
            return band.letter, band.remark
    return "-", "Not graded"


def validate_score(score_raw, max_score: Decimal) -> tuple[Decimal | None, str | None]:
    if score_raw in (None, ""):
        return None, None
    score = _to_decimal(score_raw)
    if score is None:
        return None, "Invalid score. Enter a valid number."
    if score < 0:
        return None, "Score cannot be negative."
    max_score = _to_decimal(max_score, Decimal("0")) or Decimal("0")
    if max_score > 0 and score > max_score:
        return None, f"Score cannot exceed {max_score}."
    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), None


def score_result(assessment: Assessment, score: AssessmentScore | None) -> ScoreResult:
    value = score.score if score else None
    pct = percentage(value, assessment.max_score)
    grade, remark = grade_for_percentage(pct)
    return ScoreResult(
        score=value,
        max_score=assessment.max_score,
        percentage=pct,
        grade=grade,
        remark=remark,
        note=score.note if score else "",
        report_comment=score.report_comment if score else "",
        report_comment_ai_assisted=bool(score.report_comment_ai_assisted) if score else False,
        is_missing=value is None,
    )


def active_offerings_for_student(student: StudentProfile) -> QuerySet:
    return CourseOffering.objects.filter(
        enrollment__student=student,
        enrollment__status=Enrollment.ACTIVE,
        is_active=True,
    ).select_related("course", "term", "term__year", "class_group", "teacher").distinct()


def published_assessments_for_student(student: StudentProfile) -> QuerySet:
    return Assessment.objects.filter(
        offering__in=active_offerings_for_student(student),
        is_published=True,
    ).select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "offering__teacher",
    ).order_by("offering__term__year__name", "offering__term__order", "offering__course__name", "date", "name")


def score_map_for_student(student: StudentProfile, assessments: Iterable[Assessment]) -> dict[int, AssessmentScore]:
    assessment_ids = [assessment.id for assessment in assessments]
    return {
        score.assessment_id: score
        for score in AssessmentScore.objects.filter(student=student, assessment_id__in=assessment_ids)
        .select_related("assessment", "student", "graded_by")
    }


def build_course_result(offering: CourseOffering, assessments: list[Assessment], score_map: dict[int, AssessmentScore]) -> CourseResult:
    assessment_rows = []
    weighted_total = Decimal("0")
    total_weight = Decimal("0")
    simple_total = Decimal("0")
    completed_count = 0

    for assessment in assessments:
        score_obj = score_map.get(assessment.id)
        result = score_result(assessment, score_obj)
        if result.percentage is not None:
            completed_count += 1
            simple_total += result.percentage
            weight = _to_decimal(assessment.weight)
            if weight is not None and weight > 0:
                total_weight += weight
                weighted_total += (result.percentage * weight)

        assessment_rows.append(
            {
                "assessment": assessment,
                "score": score_obj,
                "result": result,
            }
        )

    assessment_count = len(assessments)
    weighted_percentage = None
    if total_weight > 0:
        weighted_percentage = quantize_percent(weighted_total / total_weight)

    simple_percentage = None
    if completed_count > 0:
        simple_percentage = quantize_percent(simple_total / Decimal(completed_count))

    final_percentage = weighted_percentage if weighted_percentage is not None else simple_percentage
    grade, remark = grade_for_percentage(final_percentage)

    return CourseResult(
        offering=offering,
        assessments=assessment_rows,
        total_weight=total_weight,
        weighted_percentage=weighted_percentage,
        simple_percentage=simple_percentage,
        grade=grade,
        remark=remark,
        completed_count=completed_count,
        assessment_count=assessment_count,
    )


def build_report_card(student: StudentProfile) -> ReportCard:
    assessments = list(published_assessments_for_student(student))
    score_map = score_map_for_student(student, assessments)

    by_offering: dict[int, list[Assessment]] = {}
    offerings: dict[int, CourseOffering] = {}
    for assessment in assessments:
        by_offering.setdefault(assessment.offering_id, []).append(assessment)
        offerings[assessment.offering_id] = assessment.offering

    course_results = [
        build_course_result(offerings[offering_id], items, score_map)
        for offering_id, items in by_offering.items()
    ]

    completed_course_percentages = [
        result.weighted_percentage if result.weighted_percentage is not None else result.simple_percentage
        for result in course_results
        if (result.weighted_percentage if result.weighted_percentage is not None else result.simple_percentage) is not None
    ]
    overall_percentage = None
    if completed_course_percentages:
        overall_percentage = quantize_percent(
            sum(completed_course_percentages, Decimal("0")) / Decimal(len(completed_course_percentages))
        )

    overall_grade, overall_remark = grade_for_percentage(overall_percentage)
    completed_assessment_count = sum(result.completed_count for result in course_results)

    return ReportCard(
        student=student,
        course_results=course_results,
        overall_percentage=overall_percentage,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        published_assessment_count=len(assessments),
        completed_assessment_count=completed_assessment_count,
    )


def parent_can_access_student(parent: ParentProfile, student: StudentProfile) -> bool:
    return ParentStudentLink.objects.filter(parent=parent, student=student).exists()


def parent_linked_students(parent: ParentProfile):
    return StudentProfile.objects.filter(parentstudentlink__parent=parent).select_related("campus", "stream", "stream__class_group").distinct().order_by("last_name", "first_name")
