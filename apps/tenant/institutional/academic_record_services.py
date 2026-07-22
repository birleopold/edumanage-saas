from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .academic_records import (
    AcademicAttemptPolicy,
    AcademicStanding,
    CourseAttempt,
    SemesterRegistration,
    resolve_attempt_policy_for_registration,
)


ZERO = Decimal("0.00")


def _q(value):
    return Decimal(str(value or 0)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def completed_attempts(student, academic_term=None):
    qs = CourseAttempt.objects.filter(
        registration__student=student,
        status=CourseAttempt.COMPLETED,
        counts_toward_gpa=True,
        grade_point__isnull=False,
    ).select_related(
        "registration",
        "registration__academic_term",
        "registration__program",
        "course",
    )
    if academic_term is not None:
        qs = qs.filter(registration__academic_term=academic_term)
    return qs


def select_counted_attempts(student, academic_term=None):
    attempts = list(completed_attempts(student, academic_term))
    grouped = defaultdict(list)
    for attempt in attempts:
        grouped[attempt.course_id].append(attempt)

    selected = []
    for rows in grouped.values():
        rows.sort(
            key=lambda row: (
                row.registration.academic_term.year.name,
                row.registration.academic_term.order,
                row.attempt_number,
                row.pk,
            )
        )
        policy = resolve_attempt_policy_for_registration(rows[-1].registration)
        replacement_mode = (
            policy.replacement_mode if policy else AcademicAttemptPolicy.LATEST
        )
        if replacement_mode == AcademicAttemptPolicy.BEST:
            selected.append(
                max(
                    rows,
                    key=lambda row: (
                        row.grade_point or ZERO,
                        row.attempt_number,
                        row.pk,
                    ),
                )
            )
        elif replacement_mode == AcademicAttemptPolicy.ORIGINAL:
            selected.append(rows[0])
        else:
            selected.append(rows[-1])
    return sorted(selected, key=lambda row: row.course.name)


def calculate_gpa(attempts):
    weighted = ZERO
    credits = ZERO
    for attempt in attempts:
        if attempt.grade_point is None or not attempt.counts_toward_gpa:
            continue
        attempt_credits = Decimal(attempt.credits)
        weighted += Decimal(attempt.grade_point) * attempt_credits
        credits += attempt_credits
    return (_q(weighted / credits) if credits else ZERO), _q(credits)


def semester_gpa(student, academic_term):
    return calculate_gpa(select_counted_attempts(student, academic_term))


def cumulative_gpa(student):
    return calculate_gpa(select_counted_attempts(student))


def academic_standing_code(policy, cumulative_value, *, programme_completed=False):
    if programme_completed:
        return AcademicStanding.COMPLETED
    if policy and policy.dismissal_cgpa is not None:
        if cumulative_value < policy.dismissal_cgpa:
            return AcademicStanding.DISMISSED
    if policy and cumulative_value < policy.probation_cgpa:
        return AcademicStanding.PROBATION
    if policy and cumulative_value == policy.probation_cgpa:
        return AcademicStanding.WARNING
    return AcademicStanding.GOOD


@transaction.atomic
def calculate_academic_standing(
    registration: SemesterRegistration,
    *,
    actor=None,
    programme_completed=False,
):
    registration.full_clean()
    semester_attempts = select_counted_attempts(
        registration.student,
        registration.academic_term,
    )
    cumulative_attempts = select_counted_attempts(registration.student)
    semester_value, attempted_credits = calculate_gpa(semester_attempts)
    cumulative_value, _ = calculate_gpa(cumulative_attempts)
    policy = resolve_attempt_policy_for_registration(registration)
    pass_point = policy.pass_grade_point if policy else Decimal("2.00")
    earned_credits = _q(
        sum(
            (
                Decimal(attempt.credits)
                for attempt in semester_attempts
                if Decimal(attempt.grade_point or 0) >= pass_point
            ),
            ZERO,
        )
    )
    standing_code = academic_standing_code(
        policy,
        cumulative_value,
        programme_completed=programme_completed,
    )
    progression = {
        AcademicStanding.GOOD: "PROGRESS",
        AcademicStanding.WARNING: "PROGRESS_WITH_WARNING",
        AcademicStanding.PROBATION: "REVIEW",
        AcademicStanding.DISMISSED: "DO_NOT_PROGRESS",
        AcademicStanding.COMPLETED: "PROGRAMME_COMPLETED",
    }[standing_code]
    snapshot = {
        "policy_id": getattr(policy, "pk", None),
        "replacement_mode": getattr(policy, "replacement_mode", "LATEST"),
        "semester_attempt_ids": [attempt.pk for attempt in semester_attempts],
        "cumulative_attempt_ids": [attempt.pk for attempt in cumulative_attempts],
        "calculated_at": timezone.now().isoformat(),
    }
    standing, _ = AcademicStanding.objects.update_or_create(
        student=registration.student,
        academic_term=registration.academic_term,
        defaults={
            "semester_gpa": semester_value,
            "cumulative_gpa": cumulative_value,
            "attempted_credits": attempted_credits,
            "earned_credits": earned_credits,
            "standing": standing_code,
            "progression_decision": progression,
            "snapshot": snapshot,
            "calculated_at": timezone.now(),
            "calculated_by": actor,
        },
    )
    return standing


def academic_record_readiness():
    policies = list(AcademicAttemptPolicy.objects.all())
    registrations = list(
        SemesterRegistration.objects.select_related(
            "student",
            "academic_term",
            "program",
        )
    )
    attempts = list(
        CourseAttempt.objects.select_related(
            "registration",
            "registration__student",
            "registration__academic_term",
            "course",
            "offering",
            "replaced_attempt",
        )
    )
    invalid_policies = []
    invalid_registrations = []
    invalid_attempts = []
    for policy in policies:
        try:
            policy.full_clean()
        except ValidationError as exc:
            invalid_policies.append({"policy": policy, "errors": exc.messages})
    for registration in registrations:
        try:
            registration.full_clean()
        except ValidationError as exc:
            invalid_registrations.append(
                {"registration": registration, "errors": exc.messages}
            )
    for attempt in attempts:
        try:
            attempt.full_clean()
        except ValidationError as exc:
            invalid_attempts.append({"attempt": attempt, "errors": exc.messages})
    completed_terms_without_standing = SemesterRegistration.objects.filter(
        status=SemesterRegistration.COMPLETED,
        academic_term__academic_standings__isnull=True,
    ).distinct().count()
    checks = {
        "policies_valid": not invalid_policies,
        "registrations_valid": not invalid_registrations,
        "attempts_valid": not invalid_attempts,
        "completed_terms_have_standing": completed_terms_without_standing == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "policy_count": len(policies),
        "registration_count": len(registrations),
        "attempt_count": len(attempts),
        "standing_count": AcademicStanding.objects.count(),
        "invalid_policy_count": len(invalid_policies),
        "invalid_registration_count": len(invalid_registrations),
        "invalid_attempt_count": len(invalid_attempts),
        "completed_term_without_standing_count": completed_terms_without_standing,
        "invalid_policies": invalid_policies,
        "invalid_registrations": invalid_registrations,
        "invalid_attempts": invalid_attempts,
    }
