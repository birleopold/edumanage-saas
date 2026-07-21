from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant.students.models import StudentProfile

from .hardening_models import GuardianContactLog, WelfareCaseEscalation
from .models import (
    BedAllocation,
    BoardingLeave,
    BoardingProfile,
    HostelRollCall,
    HostelRollCallEntry,
    WelfareCase,
    WelfareCaseAction,
)


def confirmed_guardian_contact_for_leave(leave: BoardingLeave):
    return leave.guardian_contact_logs.filter(
        purpose__in=[GuardianContactLog.LEAVE_APPROVAL, GuardianContactLog.DEPARTURE],
        outcome=GuardianContactLog.CONFIRMED,
    ).order_by("-occurred_at").first()


@transaction.atomic
def record_guardian_contact(
    *,
    student: StudentProfile,
    purpose: str,
    method: str,
    outcome: str,
    contact_name: str = "",
    contact_phone: str = "",
    note: str = "",
    occurred_at=None,
    recorded_by=None,
    boarding_leave: BoardingLeave | None = None,
    welfare_case: WelfareCase | None = None,
    roll_call_entry: HostelRollCallEntry | None = None,
) -> GuardianContactLog:
    log = GuardianContactLog(
        student=student,
        boarding_leave=boarding_leave,
        welfare_case=welfare_case,
        roll_call_entry=roll_call_entry,
        purpose=purpose,
        method=method,
        outcome=outcome,
        contact_name=(contact_name or "").strip(),
        contact_phone=(contact_phone or "").strip(),
        note=(note or "").strip(),
        occurred_at=occurred_at or timezone.now(),
        recorded_by=recorded_by,
    )
    log.full_clean()
    log.save()
    return log


@transaction.atomic
def escalate_welfare_case(
    case: WelfareCase,
    *,
    level: str,
    reason: str,
    user=None,
    response_due_at=None,
    guardian_contact_required=False,
) -> WelfareCaseEscalation:
    reason = (reason or "").strip()
    escalation, _ = WelfareCaseEscalation.objects.select_for_update().get_or_create(
        welfare_case=case
    )
    escalation.level = level
    escalation.reason = reason
    escalation.response_due_at = response_due_at
    escalation.guardian_contact_required = bool(guardian_contact_required)
    escalation.escalated_by = user
    escalation.escalated_at = timezone.now() if level != WelfareCaseEscalation.NONE else None
    escalation.last_reviewed_at = timezone.now()
    escalation.full_clean()
    escalation.save()

    if level != WelfareCaseEscalation.NONE:
        WelfareCaseAction.objects.create(
            welfare_case=case,
            action_type=WelfareCaseAction.ESCALATION,
            note=f"Escalated to {escalation.get_level_display()}: {reason}",
            next_follow_up_at=response_due_at,
            performed_by=user,
        )
        if case.status == WelfareCase.OPEN:
            case.status = WelfareCase.MONITORING
            case.save(update_fields=["status", "updated_at"])
    return escalation


def _departed_leave_at(student_id: int, at):
    return (
        BoardingLeave.objects.filter(
            student_id=student_id,
            status=BoardingLeave.DEPARTED,
            expected_departure_at__lte=at,
            expected_return_at__gte=at,
        )
        .order_by("-expected_departure_at")
        .first()
    )


@transaction.atomic
def reconcile_roll_call_leave_statuses(
    roll_call: HostelRollCall,
    *,
    dry_run=False,
) -> dict:
    if roll_call.status != HostelRollCall.DRAFT:
        raise ValidationError("Only draft roll calls can be reconciled.")

    entries = list(
        roll_call.entries.select_related("student", "boarding_leave").order_by("pk")
    )
    set_on_leave = []
    reset_to_unmarked = []
    preserved_explicit = 0

    for entry in entries:
        leave = _departed_leave_at(entry.student_id, roll_call.taken_at)
        if entry.presence in {
            HostelRollCallEntry.PRESENT,
            HostelRollCallEntry.ABSENT,
            HostelRollCallEntry.EXCUSED,
            HostelRollCallEntry.SICK,
        }:
            preserved_explicit += 1
            continue
        if leave and (
            entry.presence != HostelRollCallEntry.ON_LEAVE
            or entry.boarding_leave_id != leave.pk
        ):
            set_on_leave.append((entry, leave))
        elif not leave and (
            entry.presence == HostelRollCallEntry.ON_LEAVE
            or entry.boarding_leave_id is not None
        ):
            reset_to_unmarked.append(entry)

    if not dry_run:
        now = timezone.now()
        for entry, leave in set_on_leave:
            entry.presence = HostelRollCallEntry.ON_LEAVE
            entry.boarding_leave = leave
            entry.checked_at = now
            entry.save(update_fields=["presence", "boarding_leave", "checked_at"])
        for entry in reset_to_unmarked:
            entry.presence = HostelRollCallEntry.UNMARKED
            entry.boarding_leave = None
            entry.checked_at = now
            entry.save(update_fields=["presence", "boarding_leave", "checked_at"])

    return {
        "entry_count": len(entries),
        "set_on_leave_count": len(set_on_leave),
        "reset_to_unmarked_count": len(reset_to_unmarked),
        "preserved_explicit_count": preserved_explicit,
        "change_count": len(set_on_leave) + len(reset_to_unmarked),
        "dry_run": bool(dry_run),
    }


def student_boarding_readiness(student: StudentProfile) -> dict:
    profile = BoardingProfile.objects.filter(student=student, is_active=True).first()
    allocation = BedAllocation.objects.filter(
        student=student,
        status=BedAllocation.ACTIVE,
    ).select_related("bed", "bed__room", "bed__room__hostel").first()

    checks = {
        "profile_available": bool(profile),
        "guardian_contact_available": bool(
            profile and profile.primary_guardian_name and profile.primary_guardian_phone
        ),
        "placement_aligned": bool(
            profile
            and (
                (profile.is_boarder and allocation)
                or (not profile.is_boarder and not allocation)
            )
        ),
    }
    warnings = {
        "authorised_pickup_people_available": bool(
            profile and profile.authorised_pickup_people
        ),
        "alternate_contact_available": bool(
            profile and profile.alternate_contact_name and profile.alternate_contact_phone
        ),
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "warnings": warnings,
        "profile": profile,
        "allocation": allocation,
    }


def phase7_operational_readiness() -> dict:
    boarder_profiles = BoardingProfile.objects.filter(
        is_active=True,
        student__is_active=True,
        boarding_status__in=[
            BoardingProfile.BOARDER,
            BoardingProfile.WEEKLY,
            BoardingProfile.FLEXIBLE,
        ],
    )
    missing_guardian_contact = boarder_profiles.filter(
        primary_guardian_phone=""
    ).count() + boarder_profiles.filter(primary_guardian_name="").exclude(
        primary_guardian_phone=""
    ).count()

    departed_without_confirmation = (
        BoardingLeave.objects.filter(status=BoardingLeave.DEPARTED)
        .exclude(
            guardian_contact_logs__purpose__in=[
                GuardianContactLog.LEAVE_APPROVAL,
                GuardianContactLog.DEPARTURE,
            ],
            guardian_contact_logs__outcome=GuardianContactLog.CONFIRMED,
        )
        .distinct()
        .count()
    )

    overdue_response_count = WelfareCaseEscalation.objects.filter(
        response_due_at__lt=timezone.now(),
        welfare_case__status__in=[
            WelfareCase.OPEN,
            WelfareCase.MONITORING,
            WelfareCase.REFERRED,
        ],
    ).count()
    unassigned_high_priority_count = WelfareCase.objects.filter(
        severity__in=[WelfareCase.HIGH, WelfareCase.CRITICAL],
        assigned_to__isnull=True,
    ).exclude(status__in=[WelfareCase.RESOLVED, WelfareCase.CLOSED]).count()

    draft_roll_calls = list(
        HostelRollCall.objects.filter(status=HostelRollCall.DRAFT).prefetch_related(
            "entries__student", "entries__boarding_leave"
        )
    )
    mismatched_roll_calls = 0
    pending_reconciliation_changes = 0
    for roll_call in draft_roll_calls:
        summary = reconcile_roll_call_leave_statuses(roll_call, dry_run=True)
        if summary["change_count"]:
            mismatched_roll_calls += 1
            pending_reconciliation_changes += summary["change_count"]

    checks = {
        "boarder_guardian_contacts_complete": missing_guardian_contact == 0,
        "departures_confirmed": departed_without_confirmation == 0,
        "case_responses_current": overdue_response_count == 0,
        "draft_roll_calls_reconciled": mismatched_roll_calls == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "boarder_missing_guardian_contact_count": missing_guardian_contact,
        "departed_without_confirmation_count": departed_without_confirmation,
        "overdue_case_response_count": overdue_response_count,
        "unassigned_high_priority_case_count": unassigned_high_priority_count,
        "draft_roll_call_mismatch_count": mismatched_roll_calls,
        "pending_roll_call_reconciliation_change_count": pending_reconciliation_changes,
        "guardian_contact_log_count": GuardianContactLog.objects.count(),
        "escalated_case_count": WelfareCaseEscalation.objects.exclude(
            level=WelfareCaseEscalation.NONE
        ).count(),
    }
