from dataclasses import dataclass, replace
from decimal import Decimal

from apps.tenant.students.models import StudentProfile

from .grading_services import (
    calculate_report_summary,
    grade_for_percentage,
    report_rule_for_profile,
    resolve_grading_profile,
)
from .models import Assessment, AssessmentScore, AssessmentWeightingScheme
from .services import (
    ComponentResult,
    ScoreResult,
    build_report_card as build_legacy_report_card,
    score_result as legacy_score_result,
)


@dataclass(frozen=True)
class ConfiguredCourseResult:
    offering: object
    assessments: list[dict]
    total_weight: Decimal
    weighted_percentage: Decimal | None
    simple_percentage: Decimal | None
    grade: str
    remark: str
    completed_count: int
    assessment_count: int
    scheme: AssessmentWeightingScheme | None = None
    is_complete: bool = True
    component_results: list[ComponentResult] | None = None
    grading_profile: object | None = None


@dataclass(frozen=True)
class ConfiguredReportCard:
    student: StudentProfile
    course_results: list[ConfiguredCourseResult]
    overall_percentage: Decimal | None
    overall_grade: str
    overall_remark: str
    published_assessment_count: int
    completed_assessment_count: int
    grading_profile: object | None = None
    report_rule: object | None = None
    promotion_status: str = ""
    passed_course_count: int = 0
    failed_course_count: int = 0
    is_complete: bool = True


def score_result(assessment: Assessment, score: AssessmentScore | None) -> ScoreResult:
    legacy = legacy_score_result(assessment, score)
    profile = resolve_grading_profile(assessment.offering)
    if not profile:
        return legacy
    grade, remark = grade_for_percentage(legacy.percentage, profile)
    return replace(legacy, grade=grade, remark=remark)


def _course_percentage(course):
    if course.scheme:
        return course.weighted_percentage
    return course.weighted_percentage if course.weighted_percentage is not None else course.simple_percentage


def _configured_course(course) -> ConfiguredCourseResult:
    profile = resolve_grading_profile(course.offering)
    assessment_rows = []
    for row in course.assessments:
        assessment_rows.append(
            {
                **row,
                "result": score_result(row["assessment"], row.get("score")),
            }
        )
    grade = course.grade
    remark = course.remark
    if profile:
        grade, remark = grade_for_percentage(_course_percentage(course), profile)
    return ConfiguredCourseResult(
        offering=course.offering,
        assessments=assessment_rows,
        total_weight=course.total_weight,
        weighted_percentage=course.weighted_percentage,
        simple_percentage=course.simple_percentage,
        grade=grade,
        remark=remark,
        completed_count=course.completed_count,
        assessment_count=course.assessment_count,
        scheme=course.scheme,
        is_complete=course.is_complete,
        component_results=course.component_results,
        grading_profile=profile,
    )


def build_report_card(student: StudentProfile) -> ConfiguredReportCard:
    legacy = build_legacy_report_card(student)
    courses = [_configured_course(course) for course in legacy.course_results]
    summary = calculate_report_summary(courses)
    profile = summary["profile"]

    if profile:
        overall_percentage = summary["overall_percentage"]
        overall_grade, overall_remark = grade_for_percentage(overall_percentage, profile)
        passed_count = summary["passed_course_count"]
        failed_count = summary["failed_course_count"]
        is_complete = summary["is_complete"]
        promotion_status = summary["promotion_status"]
    else:
        overall_percentage = legacy.overall_percentage
        overall_grade = legacy.overall_grade
        overall_remark = legacy.overall_remark
        passed_count = 0
        failed_count = 0
        is_complete = True
        promotion_status = ""

    return ConfiguredReportCard(
        student=student,
        course_results=courses,
        overall_percentage=overall_percentage,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        published_assessment_count=legacy.published_assessment_count,
        completed_assessment_count=legacy.completed_assessment_count,
        grading_profile=profile,
        report_rule=report_rule_for_profile(profile),
        promotion_status=promotion_status,
        passed_course_count=passed_count,
        failed_course_count=failed_count,
        is_complete=is_complete,
    )
