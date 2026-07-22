from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.tenant.students.models import StudentProfile

from .grading_results import ConfiguredCourseResult, build_report_card
from .grading_services import (
    calculate_report_summary,
    grade_for_percentage as configured_grade_for_percentage,
    report_rule_for_profile,
)
from .services import grade_for_percentage as fallback_grade_for_percentage
from .services import quantize_percent


@dataclass(frozen=True)
class ResultSnapshot:
    student: StudentProfile
    academic_term: object | None
    course_results: list[ConfiguredCourseResult]
    overall_percentage: Decimal | None
    overall_grade: str
    overall_remark: str
    grading_profile: object | None
    report_rule: object | None
    promotion_status: str
    passed_course_count: int
    failed_course_count: int
    is_complete: bool
    published_assessment_count: int
    completed_assessment_count: int


def course_percentage(course: ConfiguredCourseResult):
    if course.scheme:
        return course.weighted_percentage
    return (
        course.weighted_percentage
        if course.weighted_percentage is not None
        else course.simple_percentage
    )


def build_result_snapshot(
    student: StudentProfile,
    *,
    academic_term=None,
) -> ResultSnapshot:
    report = build_report_card(student)
    courses = list(report.course_results)
    if academic_term is not None:
        courses = [
            course
            for course in courses
            if course.offering.term_id == academic_term.pk
        ]

    summary = calculate_report_summary(courses)
    profile = summary["profile"]
    if profile:
        overall_percentage = summary["overall_percentage"]
        overall_grade, overall_remark = configured_grade_for_percentage(
            overall_percentage,
            profile,
        )
        promotion_status = summary["promotion_status"]
        passed_count = summary["passed_course_count"]
        failed_count = summary["failed_course_count"]
        is_complete = summary["is_complete"]
    else:
        values = [
            course_percentage(course)
            for course in courses
            if course_percentage(course) is not None
        ]
        overall_percentage = None
        if values:
            overall_percentage = quantize_percent(
                sum(values, Decimal("0")) / Decimal(len(values))
            )
        overall_grade, overall_remark = fallback_grade_for_percentage(
            overall_percentage
        )
        promotion_status = ""
        passed_count = sum(1 for value in values if value >= Decimal("50"))
        failed_count = sum(1 for value in values if value < Decimal("50"))
        is_complete = all(course.is_complete for course in courses)

    return ResultSnapshot(
        student=student,
        academic_term=academic_term,
        course_results=courses,
        overall_percentage=overall_percentage,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        grading_profile=profile,
        report_rule=report_rule_for_profile(profile),
        promotion_status=promotion_status,
        passed_course_count=passed_count,
        failed_course_count=failed_count,
        is_complete=is_complete,
        published_assessment_count=sum(
            course.assessment_count for course in courses
        ),
        completed_assessment_count=sum(
            course.completed_count for course in courses
        ),
    )


def grade_point_for_course(course: ConfiguredCourseResult):
    profile = course.grading_profile
    if not profile or not course.grade:
        return None
    grade_range = profile.grading_scale.ranges.filter(
        grade=course.grade
    ).order_by("order", "pk").first()
    return grade_range.grade_point if grade_range else None


def course_result_rows(snapshot: ResultSnapshot) -> list[dict]:
    rows = []
    for course_result in snapshot.course_results:
        percentage = course_percentage(course_result)
        rows.append(
            {
                "course": course_result.offering.course,
                "offering": course_result.offering,
                "percentage": percentage,
                "grade": course_result.grade,
                "remark": course_result.remark,
                "grade_point": grade_point_for_course(course_result),
                "credits": course_result.offering.course.credits or 1,
                "is_complete": course_result.is_complete,
                "scheme": course_result.scheme,
                "grading_profile": course_result.grading_profile,
                "component_results": course_result.component_results or [],
            }
        )
    return sorted(rows, key=lambda row: row["course"].name)
