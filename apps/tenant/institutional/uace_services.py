from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant.academics.pathway_extensions import (
    SubjectCombinationPolicy,
    SubjectRoleProfile,
)

from .models import LearnerSubjectCombination


PRINCIPAL_ROLES = {SubjectRoleProfile.PRINCIPAL}
SUBSIDIARY_ROLES = {
    SubjectRoleProfile.SUBSIDIARY,
    SubjectRoleProfile.GENERAL_PAPER,
    SubjectRoleProfile.SUBSIDIARY_ICT,
    SubjectRoleProfile.SUBSIDIARY_MATHEMATICS,
}


def active_combination_registration(student, academic_year=None):
    qs = LearnerSubjectCombination.objects.filter(
        student=student,
        is_active=True,
    ).select_related(
        "combination",
        "combination__pathway",
        "academic_year",
    )
    if academic_year is not None:
        qs = qs.filter(academic_year=academic_year)
    return qs.order_by("-academic_year__name", "-registered_on", "-pk").first()


def role_profiles_for_combination(combination):
    rows = combination.course_memberships.filter(is_active=True).select_related(
        "course",
        "academic_role_profile",
    )
    result = {}
    for membership in rows:
        try:
            role = membership.academic_role_profile
        except SubjectRoleProfile.DoesNotExist:
            role = None
        result[membership.course_id] = {
            "membership": membership,
            "role": role,
        }
    return result


def combination_structure_errors(combination) -> list[str]:
    try:
        policy = combination.academic_policy
    except SubjectCombinationPolicy.DoesNotExist:
        return ["The combination has no academic role and capacity policy."]
    try:
        policy.full_clean()
    except ValidationError as exc:
        return list(exc.messages)

    profiles = role_profiles_for_combination(combination)
    missing_roles = [
        row["membership"].course.name
        for row in profiles.values()
        if row["role"] is None
    ]
    errors = []
    if missing_roles:
        errors.append(
            "Missing academic roles for: " + ", ".join(sorted(missing_roles))
        )
    principal_count = sum(
        1
        for row in profiles.values()
        if row["role"] and row["role"].academic_role in PRINCIPAL_ROLES
    )
    subsidiary_count = sum(
        1
        for row in profiles.values()
        if row["role"] and row["role"].academic_role in SUBSIDIARY_ROLES
    )
    if principal_count < policy.minimum_principal_subjects:
        errors.append(
            f"Principal subjects are {principal_count}; minimum is {policy.minimum_principal_subjects}."
        )
    if (
        policy.maximum_principal_subjects is not None
        and principal_count > policy.maximum_principal_subjects
    ):
        errors.append(
            f"Principal subjects are {principal_count}; maximum is {policy.maximum_principal_subjects}."
        )
    if subsidiary_count < policy.minimum_subsidiary_subjects:
        errors.append(
            f"Subsidiary subjects are {subsidiary_count}; minimum is {policy.minimum_subsidiary_subjects}."
        )
    if (
        policy.maximum_subsidiary_subjects is not None
        and subsidiary_count > policy.maximum_subsidiary_subjects
    ):
        errors.append(
            f"Subsidiary subjects are {subsidiary_count}; maximum is {policy.maximum_subsidiary_subjects}."
        )
    if policy.require_general_paper:
        general_paper_count = sum(
            1
            for row in profiles.values()
            if row["role"]
            and row["role"].academic_role == SubjectRoleProfile.GENERAL_PAPER
        )
        if general_paper_count != 1:
            errors.append("The combination must contain exactly one General Paper subject.")
    return errors


def registration_capacity_errors(registration) -> list[str]:
    try:
        policy = registration.combination.academic_policy
    except SubjectCombinationPolicy.DoesNotExist:
        return ["The selected combination has no capacity policy."]
    if policy.maximum_students is None:
        return []
    used = LearnerSubjectCombination.objects.filter(
        combination=registration.combination,
        academic_year=registration.academic_year,
        is_active=True,
    )
    if registration.pk:
        used = used.exclude(pk=registration.pk)
    if used.count() >= policy.maximum_students:
        return ["The subject combination has reached its configured capacity."]
    return []


def calculate_uace_points(
    student,
    result_rows,
    *,
    academic_year=None,
    settings=None,
):
    settings = dict(settings or {})
    registration = active_combination_registration(student, academic_year)
    if registration is None:
        return {
            "configured": False,
            "incomplete": True,
            "reason": "No active subject combination registration was found.",
            "principal_points": 0,
            "subsidiary_points": 0,
            "total_points": 0,
            "subject_points": [],
        }
    structure_errors = combination_structure_errors(registration.combination)
    if structure_errors:
        return {
            "configured": False,
            "incomplete": True,
            "reason": "; ".join(structure_errors),
            "principal_points": 0,
            "subsidiary_points": 0,
            "total_points": 0,
            "subject_points": [],
            "combination": registration.combination,
            "registration": registration,
        }

    roles = role_profiles_for_combination(registration.combination)
    grade_points = settings.get(
        "principal_grade_points",
        {"A": 6, "B": 5, "C": 4, "D": 3, "E": 2, "O": 1, "F": 0},
    )
    subsidiary_pass_percentage = Decimal(
        str(settings.get("subsidiary_pass_percentage", 50))
    )
    principal_points = 0
    subsidiary_points = 0
    subject_points = []
    result_course_ids = set()
    for row in result_rows:
        course_id = row["course"].pk
        role_row = roles.get(course_id)
        if not role_row or not role_row["role"]:
            continue
        result_course_ids.add(course_id)
        role = role_row["role"]
        points = 0
        if role.contributes_principal_points:
            points = int(grade_points.get(row["grade"], 0))
            principal_points += points
        elif role.contributes_subsidiary_points:
            percentage = row.get("percentage")
            points = int(
                percentage is not None
                and Decimal(str(percentage)) >= subsidiary_pass_percentage
            )
            subsidiary_points += points
        subject_points.append(
            {
                "course": row["course"],
                "role": role.academic_role,
                "grade": row.get("grade", ""),
                "percentage": row.get("percentage"),
                "points": points,
            }
        )

    required_missing = [
        role_row["membership"].course.name
        for course_id, role_row in roles.items()
        if role_row["role"]
        and role_row["role"].required_for_completion
        and course_id not in result_course_ids
    ]
    incomplete = bool(required_missing)
    return {
        "configured": True,
        "incomplete": incomplete,
        "reason": (
            "Missing required results for: " + ", ".join(sorted(required_missing))
            if required_missing
            else ""
        ),
        "principal_points": principal_points,
        "subsidiary_points": subsidiary_points,
        "total_points": principal_points + subsidiary_points,
        "subject_points": subject_points,
        "combination": registration.combination,
        "registration": registration,
    }


def uace_readiness():
    combinations = []
    invalid_combinations = []
    for policy in SubjectCombinationPolicy.objects.select_related(
        "combination",
        "combination__pathway",
    ):
        combinations.append(policy.combination)
        errors = combination_structure_errors(policy.combination)
        if errors:
            invalid_combinations.append(
                {"combination": policy.combination, "errors": errors}
            )
    registrations_without_policy = LearnerSubjectCombination.objects.filter(
        is_active=True,
        combination__academic_policy__isnull=True,
    ).count()
    over_capacity = 0
    for registration in LearnerSubjectCombination.objects.filter(
        is_active=True
    ).select_related("combination", "combination__academic_policy", "academic_year"):
        errors = registration_capacity_errors(registration)
        if errors:
            over_capacity += 1
    checks = {
        "combination_policies_valid": not invalid_combinations,
        "registrations_have_policy": registrations_without_policy == 0,
        "capacity_valid": over_capacity == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "combination_policy_count": len(combinations),
        "invalid_combination_count": len(invalid_combinations),
        "registration_without_policy_count": registrations_without_policy,
        "over_capacity_registration_count": over_capacity,
        "invalid_combinations": invalid_combinations,
    }
