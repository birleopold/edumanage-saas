from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import QuerySet

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import AttendanceEntry, AttendanceSession


@dataclass(frozen=True)
class AttendanceSummary:
    total: int
    present: int
    absent: int
    late: int
    excused: int
    marked: int
    attendance_rate: Decimal


def active_teacher_offerings(teacher: TeacherProfile) -> QuerySet:
    return CourseOffering.objects.select_related(
        "campus",
        "course",
        "term",
        "term__year",
        "class_group",
    ).filter(teacher=teacher, is_active=True)


def active_enrollment_student_ids(offering: CourseOffering) -> list[int]:
    return list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.ACTIVE)
        .values_list("student_id", flat=True)
    )


def active_enrolled_students(offering: CourseOffering) -> QuerySet:
    return StudentProfile.objects.filter(
        enrollment__offering=offering,
        enrollment__status=Enrollment.ACTIVE,
        is_active=True,
    ).distinct().order_by("last_name", "first_name", "student_id")


def student_is_enrolled_in_offering(student_id: int, offering: CourseOffering) -> bool:
    return Enrollment.objects.filter(
        offering=offering,
        student_id=student_id,
        status=Enrollment.ACTIVE,
    ).exists()


def get_or_create_attendance_session(offering: CourseOffering, session_date: date, teacher: TeacherProfile | None = None) -> AttendanceSession:
    session, _created = AttendanceSession.objects.get_or_create(
        offering=offering,
        date=session_date,
        defaults={"taken_by": teacher},
    )
    if teacher and session.taken_by_id is None:
        session.taken_by = teacher
        session.save(update_fields=["taken_by"])
    return session


def ensure_entries_for_session(session: AttendanceSession, default_status: str = AttendanceEntry.PRESENT) -> int:
    student_ids = active_enrollment_student_ids(session.offering)
    if not student_ids:
        return 0
    existing_ids = set(
        AttendanceEntry.objects.filter(session=session, student_id__in=student_ids)
        .values_list("student_id", flat=True)
    )
    missing_ids = [sid for sid in student_ids if sid not in existing_ids]
    if not missing_ids:
        return 0
    AttendanceEntry.objects.bulk_create(
        [AttendanceEntry(session=session, student_id=sid, status=default_status) for sid in missing_ids],
        ignore_conflicts=True,
    )
    return len(missing_ids)


def valid_attendance_statuses() -> set[str]:
    return {choice[0] for choice in AttendanceEntry.STATUS_CHOICES}


def save_attendance_entries(
    *,
    session: AttendanceSession,
    attendance_data: dict,
    note_data: dict | None = None,
    validate_enrollment: bool = True,
) -> int:
    note_data = note_data or {}
    valid_statuses = valid_attendance_statuses()
    allowed_student_ids = set(active_enrollment_student_ids(session.offering)) if validate_enrollment else None

    updated = 0
    for raw_student_id, status in attendance_data.items():
        try:
            student_id = int(raw_student_id)
        except (TypeError, ValueError):
            continue

        if allowed_student_ids is not None and student_id not in allowed_student_ids:
            continue
        if status not in valid_statuses:
            continue

        AttendanceEntry.objects.update_or_create(
            session=session,
            student_id=student_id,
            defaults={
                "status": status,
                "note": note_data.get(str(student_id), "") or note_data.get(student_id, "") or "",
            },
        )
        updated += 1
    return updated


def attendance_summary_from_entries(entries: QuerySet | list[AttendanceEntry], expected_total: int | None = None) -> AttendanceSummary:
    entries_list = list(entries)
    counts = Counter(entry.status for entry in entries_list)
    marked = len(entries_list)
    total = expected_total if expected_total is not None else marked
    present_equivalent = counts.get(AttendanceEntry.PRESENT, 0) + counts.get(AttendanceEntry.LATE, 0) + counts.get(AttendanceEntry.EXCUSED, 0)
    rate = Decimal("0.00")
    if total:
        rate = (Decimal(present_equivalent) / Decimal(total) * Decimal("100")).quantize(Decimal("0.01"))
    return AttendanceSummary(
        total=total,
        present=counts.get(AttendanceEntry.PRESENT, 0),
        absent=counts.get(AttendanceEntry.ABSENT, 0),
        late=counts.get(AttendanceEntry.LATE, 0),
        excused=counts.get(AttendanceEntry.EXCUSED, 0),
        marked=marked,
        attendance_rate=rate,
    )


def session_summary(session: AttendanceSession) -> AttendanceSummary:
    expected_total = Enrollment.objects.filter(offering=session.offering, status=Enrollment.ACTIVE).count()
    return attendance_summary_from_entries(
        AttendanceEntry.objects.filter(session=session),
        expected_total=expected_total,
    )


def student_attendance_entries(student: StudentProfile) -> QuerySet:
    return AttendanceEntry.objects.select_related(
        "session",
        "session__offering",
        "session__offering__course",
        "session__offering__term",
        "session__offering__term__year",
        "session__offering__class_group",
        "session__taken_by",
    ).filter(student=student).order_by("-session__date", "session__offering__course__name")


def student_attendance_summary(student: StudentProfile) -> AttendanceSummary:
    return attendance_summary_from_entries(student_attendance_entries(student))


def parent_linked_students(parent: ParentProfile) -> QuerySet:
    return StudentProfile.objects.filter(
        parentstudentlink__parent=parent,
        is_active=True,
    ).select_related("campus", "stream", "stream__class_group").distinct().order_by("last_name", "first_name")


def parent_can_view_student(parent: ParentProfile, student_id: int) -> bool:
    return ParentStudentLink.objects.filter(parent=parent, student_id=student_id).exists()
