from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Activity, ActivityMember
from .programme_models import (
    ActivityAttendance,
    ActivityParticipation,
    ActivityProgramme,
    ActivitySession,
)


def normalize_activity_code(value):
    return "-".join((value or "").strip().upper().replace("_", "-").split())


def bootstrap_activity_programmes(*, dry_run=False):
    activities = list(Activity.objects.order_by("pk"))
    existing_ids = set(ActivityProgramme.objects.values_list("activity_id", flat=True))
    missing_activities = [item for item in activities if item.pk not in existing_ids]

    memberships = list(ActivityMember.objects.order_by("pk"))
    existing_membership_ids = set(
        ActivityParticipation.objects.values_list("membership_id", flat=True)
    )
    missing_memberships = [item for item in memberships if item.pk not in existing_membership_ids]

    if not dry_run:
        used_codes = set(ActivityProgramme.objects.values_list("code", flat=True))
        profiles = []
        for activity in missing_activities:
            base = normalize_activity_code(activity.name) or f"ACTIVITY-{activity.pk}"
            code = base[:64]
            counter = 2
            while code in used_codes:
                suffix = f"-{counter}"
                code = f"{base[:64-len(suffix)]}{suffix}"
                counter += 1
            used_codes.add(code)
            profiles.append(
                ActivityProgramme(
                    activity=activity,
                    code=code,
                    participation_mode=(
                        ActivityProgramme.TEAM if activity.type == Activity.SPORT else ActivityProgramme.OPEN
                    ),
                    competitive=activity.type == Activity.SPORT,
                )
            )
        ActivityProgramme.objects.bulk_create(profiles, ignore_conflicts=True)

        programme_by_activity = {
            item.activity_id: item
            for item in ActivityProgramme.objects.filter(
                activity_id__in=[membership.activity_id for membership in missing_memberships]
            )
        }
        ActivityParticipation.objects.bulk_create(
            [
                ActivityParticipation(
                    membership=membership,
                    guardian_consent_status=(
                        ActivityParticipation.PENDING
                        if programme_by_activity.get(membership.activity_id)
                        and programme_by_activity[membership.activity_id].guardian_consent_required
                        else ActivityParticipation.NOT_REQUIRED
                    ),
                    medical_clearance_status=(
                        ActivityParticipation.PENDING
                        if programme_by_activity.get(membership.activity_id)
                        and programme_by_activity[membership.activity_id].medical_clearance_required
                        else ActivityParticipation.NOT_REQUIRED
                    ),
                )
                for membership in missing_memberships
            ],
            ignore_conflicts=True,
        )

    return {
        "activity_count": len(activities),
        "programme_created_count": len(missing_activities),
        "membership_count": len(memberships),
        "participation_created_count": len(missing_memberships),
        "dry_run": bool(dry_run),
    }


def eligible_memberships_for_session(session):
    queryset = ActivityMember.objects.filter(
        activity=session.activity,
        is_active=True,
        student__is_active=True,
    ).select_related("student", "student__campus", "activity")
    if session.group_id:
        queryset = queryset.filter(participation_profile__group=session.group)
    return queryset.order_by("student__last_name", "student__first_name")


def populate_session_attendance(session, *, dry_run=False):
    if session.status in {ActivitySession.COMPLETED, ActivitySession.LOCKED, ActivitySession.CANCELLED}:
        raise ValidationError("Only draft sessions can have their attendance roster populated.")
    memberships = list(eligible_memberships_for_session(session))
    existing_ids = set(session.attendance_entries.values_list("membership_id", flat=True))
    missing = [item for item in memberships if item.pk not in existing_ids]
    if not dry_run:
        ActivityAttendance.objects.bulk_create(
            [ActivityAttendance(session=session, membership=item) for item in missing],
            ignore_conflicts=True,
        )
    return {
        "eligible_count": len(memberships),
        "existing_count": len(memberships) - len(missing),
        "created_count": len(missing),
        "dry_run": bool(dry_run),
    }


def complete_activity_session(session):
    if session.status != ActivitySession.DRAFT:
        raise ValidationError("Only draft sessions can be completed.")
    if session.attendance_required and session.attendance_entries.filter(
        status=ActivityAttendance.UNMARKED
    ).exists():
        raise ValidationError("Every participant must be marked before completing the session.")
    session.status = ActivitySession.COMPLETED
    session.save(update_fields=["status", "updated_at"])
    return session


@transaction.atomic
def update_attendance_entry(entry, *, status, note="", user=None):
    if entry.session.status != ActivitySession.DRAFT:
        raise ValidationError("Attendance can only be changed while the session is in draft.")
    valid = {choice[0] for choice in ActivityAttendance.STATUS_CHOICES}
    if status not in valid:
        raise ValidationError("Invalid attendance status.")
    entry.status = status
    entry.note = (note or "").strip()
    entry.marked_by = user
    entry.marked_at = None if status == ActivityAttendance.UNMARKED else timezone.now()
    entry.save(update_fields=["status", "note", "marked_by", "marked_at"])
    return entry


def activity_programme_readiness():
    active_activities = Activity.objects.filter(is_active=True)
    active_memberships = ActivityMember.objects.filter(is_active=True, student__is_active=True)
    programmes = ActivityProgramme.objects.filter(activity__is_active=True)
    participation = ActivityParticipation.objects.filter(
        membership__is_active=True,
        membership__student__is_active=True,
    )

    missing_programme_count = active_activities.exclude(
        pk__in=programmes.values("activity_id")
    ).count()
    missing_participation_count = active_memberships.exclude(
        pk__in=participation.values("membership_id")
    ).count()
    over_capacity_count = sum(
        1
        for programme in programmes.exclude(capacity__isnull=True)
        if programme.activity.memberships.filter(is_active=True).count() > programme.capacity
    )
    consent_missing_count = participation.filter(
        membership__activity__programme_profile__guardian_consent_required=True
    ).exclude(guardian_consent_status=ActivityParticipation.APPROVED).count()
    medical_missing_count = participation.filter(
        membership__activity__programme_profile__medical_clearance_required=True
    ).exclude(medical_clearance_status=ActivityParticipation.APPROVED).count()
    completed_with_unmarked = ActivitySession.objects.filter(
        status__in=[ActivitySession.COMPLETED, ActivitySession.LOCKED],
        attendance_entries__status=ActivityAttendance.UNMARKED,
    ).distinct().count()

    checks = {
        "programmes_complete": missing_programme_count == 0,
        "participation_complete": missing_participation_count == 0,
        "completed_sessions_valid": completed_with_unmarked == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "activity_count": active_activities.count(),
        "programme_count": programmes.count(),
        "missing_programme_count": missing_programme_count,
        "membership_count": active_memberships.count(),
        "participation_count": participation.count(),
        "missing_participation_count": missing_participation_count,
        "over_capacity_count": over_capacity_count,
        "consent_missing_count": consent_missing_count,
        "medical_clearance_missing_count": medical_missing_count,
        "session_count": ActivitySession.objects.count(),
        "completed_session_with_unmarked_count": completed_with_unmarked,
    }


def learner_co_curricular_summary(student):
    memberships = (
        ActivityMember.objects.filter(student=student, is_active=True)
        .select_related("activity", "participation_profile", "participation_profile__group")
        .prefetch_related("achievements")
        .order_by("activity__name")
    )
    return {
        "student": student,
        "memberships": memberships,
        "achievement_count": sum(item.achievements.count() for item in memberships),
    }
