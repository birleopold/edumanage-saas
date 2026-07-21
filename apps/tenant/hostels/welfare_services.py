from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.tenant.discipline.models import Incident
from apps.tenant.sickbay.models import SickbayVisit
from apps.tenant.students.models import StudentProfile

from .models import (
    BedAllocation,
    BoardingLeave,
    BoardingProfile,
    Hostel,
    HostelRollCall,
    HostelRollCallEntry,
    WelfareCase,
)


@dataclass(frozen=True)
class WelfareTimelineItem:
    occurred_at: datetime
    kind: str
    title: str
    detail: str
    source: object


def current_bed_allocation(student: StudentProfile):
    return (
        BedAllocation.objects.filter(student=student, status=BedAllocation.ACTIVE)
        .select_related("bed", "bed__room", "bed__room__hostel")
        .first()
    )


def bootstrap_boarding_profiles(*, dry_run=False) -> dict:
    students = list(StudentProfile.objects.filter(is_active=True).order_by("pk"))
    existing_ids = set(BoardingProfile.objects.filter(student__in=students).values_list("student_id", flat=True))
    missing = [student for student in students if student.pk not in existing_ids]
    boarder_ids = set(
        BedAllocation.objects.filter(
            student__in=missing,
            status=BedAllocation.ACTIVE,
        ).values_list("student_id", flat=True)
    )
    if not dry_run:
        BoardingProfile.objects.bulk_create(
            [
                BoardingProfile(
                    student=student,
                    boarding_status=(
                        BoardingProfile.BOARDER if student.pk in boarder_ids else BoardingProfile.DAY
                    ),
                )
                for student in missing
            ],
            ignore_conflicts=True,
        )
    return {
        "student_count": len(students),
        "existing_count": len(students) - len(missing),
        "created_count": len(missing),
        "boarder_profile_count": sum(1 for student in missing if student.pk in boarder_ids),
        "day_profile_count": sum(1 for student in missing if student.pk not in boarder_ids),
        "dry_run": bool(dry_run),
    }


def active_leave_for_student(student: StudentProfile, at=None):
    at = at or timezone.now()
    return (
        BoardingLeave.objects.filter(
            student=student,
            status__in=[BoardingLeave.APPROVED, BoardingLeave.DEPARTED],
            expected_departure_at__lte=at,
            expected_return_at__gte=at,
        )
        .select_related("bed_allocation", "linked_sickbay_visit")
        .order_by("-expected_departure_at")
        .first()
    )


def roll_call_roster(hostel: Hostel, *, at=None):
    at = at or timezone.now()
    allocations = list(
        BedAllocation.objects.filter(
            bed__room__hostel=hostel,
            status=BedAllocation.ACTIVE,
            student__is_active=True,
        )
        .select_related("student", "bed", "bed__room", "bed__room__hostel")
        .order_by("bed__room__name", "bed__label", "student__last_name", "student__first_name")
    )
    leave_by_student = {
        leave.student_id: leave
        for leave in BoardingLeave.objects.filter(
            student_id__in=[item.student_id for item in allocations],
            status=BoardingLeave.DEPARTED,
            expected_departure_at__lte=at,
            expected_return_at__gte=at,
        ).select_related("student")
    }
    return [
        {
            "allocation": allocation,
            "student": allocation.student,
            "leave": leave_by_student.get(allocation.student_id),
        }
        for allocation in allocations
    ]


def populate_roll_call(roll_call: HostelRollCall, *, dry_run=False) -> dict:
    if roll_call.status == HostelRollCall.LOCKED:
        raise ValidationError("A locked roll call cannot be changed.")
    roster = roll_call_roster(roll_call.hostel, at=roll_call.taken_at)
    existing_ids = set(roll_call.entries.values_list("student_id", flat=True))
    missing = [row for row in roster if row["student"].pk not in existing_ids]
    if not dry_run:
        HostelRollCallEntry.objects.bulk_create(
            [
                HostelRollCallEntry(
                    roll_call=roll_call,
                    student=row["student"],
                    bed_allocation=row["allocation"],
                    boarding_leave=row["leave"],
                    presence=(
                        HostelRollCallEntry.ON_LEAVE if row["leave"] else HostelRollCallEntry.UNMARKED
                    ),
                )
                for row in missing
            ],
            ignore_conflicts=True,
        )
    return {
        "roster_count": len(roster),
        "existing_count": len(roster) - len(missing),
        "created_count": len(missing),
        "on_leave_count": sum(1 for row in missing if row["leave"]),
        "dry_run": bool(dry_run),
    }


def complete_roll_call(roll_call: HostelRollCall) -> HostelRollCall:
    if roll_call.status == HostelRollCall.LOCKED:
        raise ValidationError("A locked roll call cannot be changed.")
    if roll_call.entries.filter(presence=HostelRollCallEntry.UNMARKED).exists():
        raise ValidationError("Every learner must be marked before completing the roll call.")
    roll_call.status = HostelRollCall.COMPLETED
    roll_call.save(update_fields=["status", "updated_at"])
    return roll_call


def approve_leave(leave: BoardingLeave, user) -> BoardingLeave:
    if leave.status != BoardingLeave.PENDING:
        raise ValidationError("Only pending leave requests can be approved.")
    leave.status = BoardingLeave.APPROVED
    leave.approved_by = user
    leave.approved_at = timezone.now()
    leave.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return leave


def record_departure(leave: BoardingLeave, user, *, handover_to="") -> BoardingLeave:
    if leave.status != BoardingLeave.APPROVED:
        raise ValidationError("Only approved leave can be marked as departed.")
    leave.status = BoardingLeave.DEPARTED
    leave.departed_at = timezone.now()
    if handover_to:
        leave.handover_to = handover_to
    if not leave.recorded_by_id:
        leave.recorded_by = user
    leave.save(
        update_fields=["status", "departed_at", "handover_to", "recorded_by", "updated_at"]
    )
    return leave


def record_return(leave: BoardingLeave, user, *, note="") -> BoardingLeave:
    if leave.status != BoardingLeave.DEPARTED:
        raise ValidationError("Only departed learners can be marked as returned.")
    leave.status = BoardingLeave.RETURNED
    leave.returned_at = timezone.now()
    leave.return_note = note
    if not leave.recorded_by_id:
        leave.recorded_by = user
    leave.save(
        update_fields=["status", "returned_at", "return_note", "recorded_by", "updated_at"]
    )
    return leave


def resolve_welfare_case(case: WelfareCase, *, summary: str, user=None) -> WelfareCase:
    summary = (summary or "").strip()
    if not summary:
        raise ValidationError("A resolution summary is required.")
    case.status = WelfareCase.RESOLVED
    case.resolution_summary = summary
    case.resolved_at = timezone.now()
    if user and not case.assigned_to_id:
        case.assigned_to = user
    case.save(
        update_fields=[
            "status",
            "resolution_summary",
            "resolved_at",
            "assigned_to",
            "updated_at",
        ]
    )
    return case


def student_welfare_timeline(student: StudentProfile) -> list[WelfareTimelineItem]:
    items = []
    for allocation in BedAllocation.objects.filter(student=student).select_related(
        "bed", "bed__room", "bed__room__hostel"
    ):
        occurred = timezone.make_aware(
            datetime.combine(allocation.start_date or allocation.created_at.date(), datetime.min.time())
        )
        items.append(
            WelfareTimelineItem(
                occurred_at=occurred,
                kind="BOARDING",
                title="Bed allocation",
                detail=f"{allocation.bed} · {allocation.get_status_display()}",
                source=allocation,
            )
        )
    for leave in BoardingLeave.objects.filter(student=student):
        items.append(
            WelfareTimelineItem(
                occurred_at=leave.expected_departure_at,
                kind="LEAVE",
                title=leave.get_leave_type_display(),
                detail=f"{leave.get_status_display()} · expected return {leave.expected_return_at:%Y-%m-%d %H:%M}",
                source=leave,
            )
        )
    for visit in SickbayVisit.objects.filter(student=student):
        items.append(
            WelfareTimelineItem(
                occurred_at=visit.visit_at,
                kind="HEALTH",
                title=visit.complaint,
                detail=f"{visit.get_severity_display()} · {visit.get_outcome_display()}",
                source=visit,
            )
        )
    for incident in Incident.objects.filter(student=student):
        occurred_date = incident.incident_date or incident.created_at.date()
        occurred = timezone.make_aware(datetime.combine(occurred_date, datetime.min.time()))
        items.append(
            WelfareTimelineItem(
                occurred_at=occurred,
                kind="DISCIPLINE",
                title=incident.title,
                detail=f"{incident.get_severity_display()} · {incident.get_status_display()}",
                source=incident,
            )
        )
    for case in WelfareCase.objects.filter(student=student):
        items.append(
            WelfareTimelineItem(
                occurred_at=case.created_at,
                kind="WELFARE",
                title=case.title,
                detail=f"{case.get_category_display()} · {case.get_status_display()}",
                source=case,
            )
        )
    return sorted(items, key=lambda item: item.occurred_at, reverse=True)


def boarding_welfare_readiness() -> dict:
    active_students = StudentProfile.objects.filter(is_active=True)
    profiles = BoardingProfile.objects.filter(student__is_active=True)
    active_allocations = BedAllocation.objects.filter(status=BedAllocation.ACTIVE)
    boarder_profiles = profiles.filter(
        boarding_status__in=[
            BoardingProfile.BOARDER,
            BoardingProfile.WEEKLY,
            BoardingProfile.FLEXIBLE,
        ]
    )
    boarder_without_allocation = boarder_profiles.exclude(
        student_id__in=active_allocations.values("student_id")
    ).count()
    allocation_without_boarder_profile = active_allocations.exclude(
        student_id__in=boarder_profiles.values("student_id")
    ).count()
    missing_profile_count = active_students.exclude(
        pk__in=profiles.values("student_id")
    ).count()
    completed_with_unmarked = HostelRollCall.objects.filter(
        status__in=[HostelRollCall.COMPLETED, HostelRollCall.LOCKED],
        entries__presence=HostelRollCallEntry.UNMARKED,
    ).distinct().count()
    overdue_leave_count = BoardingLeave.objects.filter(
        status=BoardingLeave.DEPARTED,
        expected_return_at__lt=timezone.now(),
    ).count()
    unresolved_critical_case_count = WelfareCase.objects.filter(
        severity=WelfareCase.CRITICAL,
    ).exclude(status__in=[WelfareCase.RESOLVED, WelfareCase.CLOSED]).count()
    checks = {
        "profiles_complete": missing_profile_count == 0,
        "boarding_assignments_aligned": (
            boarder_without_allocation == 0 and allocation_without_boarder_profile == 0
        ),
        "completed_roll_calls_valid": completed_with_unmarked == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "active_student_count": active_students.count(),
        "profile_count": profiles.count(),
        "missing_profile_count": missing_profile_count,
        "active_allocation_count": active_allocations.count(),
        "boarder_without_allocation_count": boarder_without_allocation,
        "allocation_without_boarder_profile_count": allocation_without_boarder_profile,
        "roll_call_count": HostelRollCall.objects.count(),
        "completed_roll_call_with_unmarked_count": completed_with_unmarked,
        "open_case_count": WelfareCase.objects.exclude(
            status__in=[WelfareCase.RESOLVED, WelfareCase.CLOSED]
        ).count(),
        "unresolved_critical_case_count": unresolved_critical_case_count,
        "overdue_leave_count": overdue_leave_count,
    }
