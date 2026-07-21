from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from apps.tenant.academics.models import GradingScale

from .models import GradingProfile, ReportRule


def _to_decimal(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return default


def offering_level(offering):
    if offering.class_group_id and offering.class_group.level_id:
        return offering.class_group.level
    if offering.course_id and offering.course.level_id:
        return offering.course.level
    return None


def offering_program(offering):
    if offering.class_group_id and offering.class_group.program_id:
        return offering.class_group.program
    if offering.course_id and offering.course.program_id:
        return offering.course.program
    return None


def offering_stage(offering):
    level = offering_level(offering)
    if not level:
        return None
    try:
        from apps.tenant.education_frameworks.models import InstitutionEducationProfile
        from apps.tenant.education_frameworks.services import resolve_level_stage

        profile = InstitutionEducationProfile.objects.filter(is_active=True).first()
        return resolve_level_stage(level, profile) if profile else None
    except Exception:
        return None


def grading_scale_errors(scale: GradingScale) -> list[str]:
    errors = []
    if not scale.is_active:
        errors.append("The grading scale is inactive.")
    ranges = list(scale.ranges.order_by("min_score", "max_score", "pk"))
    if not ranges:
        return errors + ["The grading scale has no grade ranges."]
    previous_max = None
    for item in ranges:
        minimum = _to_decimal(item.min_score, Decimal("0"))
        maximum = _to_decimal(item.max_score, Decimal("0"))
        if minimum > maximum:
            errors.append(f"{item.grade}: minimum score exceeds maximum score.")
            continue
        if minimum < 0 or maximum > 100:
            errors.append(f"{item.grade}: grade ranges must stay between 0 and 100.")
        if previous_max is not None and minimum <= previous_max:
            errors.append(f"{item.grade}: overlaps another grade range.")
        previous_max = maximum
    return errors


def grading_profile_errors(profile: GradingProfile) -> list[str]:
    if not profile.grading_scale_id:
        return ["Choose a grading scale."]
    errors = grading_scale_errors(profile.grading_scale)
    duplicate = GradingProfile.objects.filter(
        campus_id=profile.campus_id,
        stage_id=profile.stage_id,
        level_id=profile.level_id,
        program_id=profile.program_id,
        academic_term_id=profile.academic_term_id,
        priority=profile.priority,
        is_active=True,
    )
    if profile.pk:
        duplicate = duplicate.exclude(pk=profile.pk)
    if profile.is_active and duplicate.exists():
        errors.append("Another active grading profile has the same scope and priority.")
    try:
        profile.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    return list(dict.fromkeys(errors))


def grading_profile_is_ready(profile: GradingProfile) -> bool:
    return bool(profile.is_active and not grading_profile_errors(profile))


def _scope_matches(profile, offering, stage, level, program) -> bool:
    return bool(
        (profile.campus_id is None or profile.campus_id == offering.campus_id)
        and (profile.stage_id is None or (stage and profile.stage_id == stage.pk))
        and (profile.level_id is None or (level and profile.level_id == level.pk))
        and (profile.program_id is None or (program and profile.program_id == program.pk))
        and (profile.academic_term_id is None or profile.academic_term_id == offering.term_id)
    )


def _specificity(profile, offering, stage, level, program) -> tuple:
    exact = sum(
        (
            bool(profile.campus_id and profile.campus_id == offering.campus_id),
            bool(profile.stage_id and stage and profile.stage_id == stage.pk),
            bool(profile.level_id and level and profile.level_id == level.pk),
            bool(profile.program_id and program and profile.program_id == program.pk),
            bool(profile.academic_term_id and profile.academic_term_id == offering.term_id),
        )
    )
    return profile.priority, exact, int(profile.is_default), profile.pk or 0


def resolve_grading_profile(offering) -> GradingProfile | None:
    level = offering_level(offering)
    program = offering_program(offering)
    stage = offering_stage(offering)
    candidates = GradingProfile.objects.filter(is_active=True).select_related(
        "grading_scale", "campus", "stage", "level", "program", "academic_term"
    ).prefetch_related("grading_scale__ranges")
    matched = [
        profile
        for profile in candidates
        if _scope_matches(profile, offering, stage, level, program)
        and grading_profile_is_ready(profile)
    ]
    return max(matched, key=lambda item: _specificity(item, offering, stage, level, program)) if matched else None


def grade_for_percentage(value, profile: GradingProfile | None) -> tuple[str, str]:
    if value is None:
        return "-", "Not graded"
    if not profile or not grading_profile_is_ready(profile):
        return "", ""
    percentage = _to_decimal(value)
    for band in profile.grading_scale.ranges.order_by("-min_score", "-max_score", "pk"):
        if band.min_score <= percentage <= band.max_score:
            return band.grade, band.remark or band.grade
    fallback_bands = (
        (Decimal("80"), "A", "Excellent"),
        (Decimal("70"), "B", "Very good"),
        (Decimal("60"), "C", "Good"),
        (Decimal("50"), "D", "Fair"),
        (Decimal("0"), "F", "Needs improvement"),
    )
    for minimum, letter, remark in fallback_bands:
        if percentage >= minimum:
            return letter, remark
    return "-", "Not graded"


def rounded_percentage(value, profile: GradingProfile | None):
    if value is None:
        return None
    places = profile.decimal_places if profile else 2
    quantum = Decimal("1").scaleb(-places)
    return _to_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def report_rule_for_profile(profile: GradingProfile | None) -> ReportRule | None:
    if not profile:
        return None
    try:
        return profile.report_rule
    except ReportRule.DoesNotExist:
        return None


def _course_percentage(course):
    if course.scheme:
        return course.weighted_percentage
    return course.weighted_percentage if course.weighted_percentage is not None else course.simple_percentage


def select_report_profile(course_results) -> GradingProfile | None:
    profiles = [item.grading_profile for item in course_results if getattr(item, "grading_profile", None)]
    if not profiles:
        return None
    counts = Counter(profile.pk for profile in profiles)
    profile_by_id = {profile.pk: profile for profile in profiles}
    return max(
        profile_by_id.values(),
        key=lambda profile: (counts[profile.pk], profile.priority, int(profile.is_default), profile.pk),
    )


def calculate_report_summary(course_results) -> dict:
    profile = select_report_profile(course_results)
    policy = profile.incomplete_result_policy if profile else GradingProfile.EXCLUDE_INCOMPLETE
    rows = []
    is_complete = True
    for course in course_results:
        value = _course_percentage(course)
        profile_marks_incomplete = bool(profile and not course.is_complete)
        if value is None or profile_marks_incomplete:
            is_complete = False
            if profile and policy == GradingProfile.REQUIRE_COMPLETE:
                return {
                    "profile": profile,
                    "overall_percentage": None,
                    "passed_course_count": 0,
                    "failed_course_count": 0,
                    "is_complete": False,
                    "promotion_status": "INCOMPLETE",
                }
            if profile and policy == GradingProfile.ZERO_INCOMPLETE:
                value = Decimal("0")
            else:
                continue
        weight = Decimal("1")
        if profile and profile.overall_aggregation == GradingProfile.CREDIT_WEIGHTED:
            weight = Decimal(str(course.offering.course.credits or 1))
        rows.append((Decimal(str(value)), weight))

    overall = None
    if rows:
        denominator = sum((weight for _, weight in rows), Decimal("0"))
        if denominator > 0:
            overall = sum((value * weight for value, weight in rows), Decimal("0")) / denominator
            overall = rounded_percentage(overall, profile)

    threshold = profile.pass_percentage if profile else Decimal("50")
    completed_values = [
        _course_percentage(course)
        for course in course_results
        if _course_percentage(course) is not None and (not profile or course.is_complete)
    ]
    passed = sum(1 for value in completed_values if value >= threshold)
    failed = sum(1 for value in completed_values if value < threshold)

    promotion_status = ""
    if profile and profile.promotion_percentage is not None:
        required_courses = profile.minimum_passed_courses or 0
        if overall is None:
            promotion_status = "INCOMPLETE"
        elif overall >= profile.promotion_percentage and passed >= required_courses:
            promotion_status = "PROMOTED"
        else:
            promotion_status = "REVIEW"

    return {
        "profile": profile,
        "overall_percentage": overall,
        "passed_course_count": passed,
        "failed_course_count": failed,
        "is_complete": is_complete,
        "promotion_status": promotion_status,
    }


def bootstrap_default_grading_profile(*, dry_run=False) -> dict:
    default_scale = GradingScale.objects.filter(is_active=True, is_default=True).prefetch_related("ranges").first()
    summary = {
        "profile_created": 0,
        "rule_created": 0,
        "profile_existing": 0,
        "scale_available": bool(default_scale),
    }
    if not default_scale or grading_scale_errors(default_scale):
        return summary
    existing = GradingProfile.objects.filter(code="DEFAULT-GRADING").first()
    if existing:
        summary["profile_existing"] = 1
        try:
            existing.report_rule
        except ReportRule.DoesNotExist:
            summary["rule_created"] = 1
            if not dry_run:
                ReportRule.objects.create(grading_profile=existing)
        return summary
    summary["profile_created"] = 1
    summary["rule_created"] = 1
    if not dry_run:
        profile = GradingProfile.objects.create(
            code="DEFAULT-GRADING",
            name=f"Default {default_scale.name}",
            grading_scale=default_scale,
            is_default=True,
            is_active=True,
        )
        ReportRule.objects.create(grading_profile=profile)
    return summary


def grading_framework_readiness() -> dict:
    profiles = list(
        GradingProfile.objects.select_related(
            "grading_scale", "campus", "stage", "level", "program", "academic_term"
        ).prefetch_related("grading_scale__ranges")
    )
    invalid = [{"profile": profile, "errors": grading_profile_errors(profile)} for profile in profiles]
    invalid = [row for row in invalid if row["errors"]]
    active_profiles = [profile for profile in profiles if profile.is_active]
    missing_rules = 0
    for profile in active_profiles:
        try:
            profile.report_rule
        except ReportRule.DoesNotExist:
            missing_rules += 1
    checks = {
        "profile_available": bool(active_profiles),
        "profiles_valid": not invalid,
        "report_rules_available": missing_rules == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "profile_count": len(profiles),
        "active_profile_count": len(active_profiles),
        "invalid_profiles": invalid,
        "invalid_profile_count": len(invalid),
        "missing_report_rule_count": missing_rules,
        "default_scale_available": GradingScale.objects.filter(is_active=True, is_default=True).exists(),
    }
