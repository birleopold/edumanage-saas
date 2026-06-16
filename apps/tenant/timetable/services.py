from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db.models import Q, QuerySet

from apps.tenant.academics.models import CourseOffering, Enrollment

from .models import Period, TimetableEntry


WEEKDAY_ORDER = [
    TimetableEntry.MON,
    TimetableEntry.TUE,
    TimetableEntry.WED,
    TimetableEntry.THU,
    TimetableEntry.FRI,
    TimetableEntry.SAT,
    TimetableEntry.SUN,
]


@dataclass(frozen=True)
class TimetableClash:
    clash_type: str
    message: str
    entry: TimetableEntry


def base_entry_queryset() -> QuerySet:
    return TimetableEntry.objects.select_related(
        "offering",
        "offering__course",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "offering__teacher",
        "period",
        "room",
    )


def active_periods() -> QuerySet:
    return Period.objects.filter(is_active=True).order_by("order", "name")


def active_entries() -> QuerySet:
    return base_entry_queryset().filter(is_active=True).order_by("weekday", "period__order", "period__name")


def weekday_choices():
    return TimetableEntry.WEEKDAY_CHOICES


def weekday_label(code: str) -> str:
    return dict(TimetableEntry.WEEKDAY_CHOICES).get(code, code)


def _exclude_self(qs: QuerySet, exclude_entry_id: int | None) -> QuerySet:
    if exclude_entry_id:
        return qs.exclude(pk=exclude_entry_id)
    return qs


def detect_timetable_clashes(
    *,
    offering: CourseOffering | None,
    weekday: str | None,
    period: Period | None,
    room=None,
    exclude_entry_id: int | None = None,
    is_active: bool = True,
) -> list[TimetableClash]:
    if not is_active or not offering or not weekday or not period:
        return []

    slot_qs = _exclude_self(
        active_entries().filter(weekday=weekday, period=period),
        exclude_entry_id,
    )
    clashes: list[TimetableClash] = []

    if offering.teacher_id:
        for entry in slot_qs.filter(offering__teacher_id=offering.teacher_id):
            clashes.append(
                TimetableClash(
                    "teacher",
                    f"Teacher clash: {offering.teacher} already has {entry.offering} during {weekday_label(weekday)} / {period}.",
                    entry,
                )
            )

    if offering.class_group_id:
        for entry in slot_qs.filter(offering__class_group_id=offering.class_group_id):
            clashes.append(
                TimetableClash(
                    "class",
                    f"Class clash: {offering.class_group} already has {entry.offering} during {weekday_label(weekday)} / {period}.",
                    entry,
                )
            )

    if room:
        for entry in slot_qs.filter(room=room):
            clashes.append(
                TimetableClash(
                    "room",
                    f"Room clash: {room} is already booked for {entry.offering} during {weekday_label(weekday)} / {period}.",
                    entry,
                )
            )

    student_ids = list(
        Enrollment.objects.filter(offering=offering, status=Enrollment.ACTIVE).values_list("student_id", flat=True)
    )
    if student_ids:
        student_clash_entries = (
            slot_qs.filter(
                offering__enrollment__student_id__in=student_ids,
                offering__enrollment__status=Enrollment.ACTIVE,
            )
            .exclude(offering=offering)
            .distinct()
        )
        for entry in student_clash_entries:
            clashes.append(
                TimetableClash(
                    "student",
                    f"Student clash: learners enrolled in {offering} also have {entry.offering} during {weekday_label(weekday)} / {period}.",
                    entry,
                )
            )

    # Remove duplicate messages caused by overlaps such as class + student clash on the same entry.
    seen = set()
    unique: list[TimetableClash] = []
    for clash in clashes:
        key = (clash.clash_type, clash.entry_id if hasattr(clash, "entry_id") else clash.entry.pk, clash.message)
        if key not in seen:
            unique.append(clash)
            seen.add(key)
    return unique


def clash_messages_for_form(**kwargs) -> list[str]:
    return [clash.message for clash in detect_timetable_clashes(**kwargs)]


def annotate_entries_with_clashes(entries: Iterable[TimetableEntry]) -> list[TimetableEntry]:
    result = []
    for entry in entries:
        clashes = detect_timetable_clashes(
            offering=entry.offering,
            weekday=entry.weekday,
            period=entry.period,
            room=entry.room,
            exclude_entry_id=entry.pk,
            is_active=entry.is_active,
        )
        entry.clashes = clashes
        entry.clash_count = len(clashes)
        result.append(entry)
    return result


def timetable_matrix(entries: Iterable[TimetableEntry], periods: Iterable[Period] | None = None) -> dict:
    periods_list = list(periods) if periods is not None else list(active_periods())
    matrix = {
        day: {period.pk: [] for period in periods_list}
        for day in WEEKDAY_ORDER
    }
    for entry in entries:
        matrix.setdefault(entry.weekday, {})
        matrix[entry.weekday].setdefault(entry.period_id, [])
        matrix[entry.weekday][entry.period_id].append(entry)
    return matrix


def entries_for_teacher(teacher) -> QuerySet:
    return active_entries().filter(offering__teacher=teacher)


def entries_for_student(student) -> QuerySet:
    offering_ids = Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True)
    return active_entries().filter(offering_id__in=offering_ids)
