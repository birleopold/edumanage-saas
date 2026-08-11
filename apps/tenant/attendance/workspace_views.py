from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile

from .device_services import resolve_policy
from .models import (
    AttendanceAdjustment,
    AttendanceDailyRecord,
    AttendanceDevice,
    AttendanceEntry,
    AttendanceEvent,
    AttendanceIdentity,
)


FIELD_CLASS = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"


class ManualStaffAttendanceForm(forms.Form):
    AUTO = "AUTO"
    STATUS_CHOICES = ((AUTO, "Calculate from reporting/sign-out times"),) + AttendanceDailyRecord.STATUS_CHOICES

    staff = forms.ModelChoiceField(queryset=StaffProfile.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(choices=STATUS_CHOICES, initial=AUTO)
    first_in = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}), label="Reporting time")
    last_out = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}), label="Sign-out time")
    note = forms.CharField(required=False, max_length=255, widget=forms.Textarea(attrs={"rows": 2}))
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required audit reason, for example manual register, office sign-in book or correction.",
    )

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        staff = StaffProfile.objects.filter(is_active=True).select_related("campus").order_by("last_name", "first_name")
        if campus_scope is not None:
            staff = staff.filter(campus=campus_scope)
        self.fields["staff"].queryset = staff
        if not self.is_bound:
            self.fields["date"].initial = timezone.localdate()
        for field in self.fields.values():
            field.widget.attrs["class"] = FIELD_CLASS

    def clean(self):
        cleaned = super().clean()
        first_in = cleaned.get("first_in")
        last_out = cleaned.get("last_out")
        if last_out and not first_in:
            self.add_error("first_in", "Enter the reporting time before entering a sign-out time.")
        if first_in and last_out and last_out < first_in:
            self.add_error("last_out", "Sign-out time cannot be earlier than reporting time.")
        if not str(cleaned.get("reason") or "").strip():
            self.add_error("reason", "Enter a reason so the manual record has an audit trail.")
        return cleaned


def _campuses_for(user):
    org = get_or_create_organization()
    scoped = get_user_campus_scope(user)
    qs = Campus.objects.filter(organization=org, is_active=True).order_by("name")
    return qs.filter(pk=scoped.pk) if scoped is not None else qs


def _staff_for(user):
    qs = StaffProfile.objects.filter(is_active=True).select_related("campus", "department", "position")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _staff_records_for(user):
    qs = AttendanceDailyRecord.objects.filter(person_type=AttendanceIdentity.STAFF).select_related(
        "staff", "campus", "policy"
    )
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _devices_for(user):
    qs = AttendanceDevice.objects.select_related("campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _parse_date(raw, default):
    try:
        return date.fromisoformat(raw) if raw else default
    except (TypeError, ValueError):
        return default


def _local_datetime(day: date, value: time | None):
    if value is None:
        return None
    naive = datetime.combine(day, value)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _policy_datetime(day: date, value: time | None):
    return _local_datetime(day, value)


def _snapshot(record: AttendanceDailyRecord):
    return {
        "status": record.status,
        "first_in": record.first_in.isoformat() if record.first_in else None,
        "last_out": record.last_out.isoformat() if record.last_out else None,
        "minutes_late": record.minutes_late,
        "minutes_early_departure": record.minutes_early_departure,
        "minutes_present": record.minutes_present,
        "manual_override": record.manual_override,
        "note": record.note,
    }


def _save_manual_staff_record(*, staff, day, requested_status, first_in_time, last_out_time, note, reason, user):
    policy = resolve_policy(AttendanceIdentity.STAFF, staff.campus)
    record, _ = AttendanceDailyRecord.objects.get_or_create(
        date=day,
        staff=staff,
        defaults={
            "person_type": AttendanceIdentity.STAFF,
            "campus": staff.campus,
            "policy": policy,
            "status": AttendanceDailyRecord.PRESENT,
        },
    )
    before = _snapshot(record)
    first_in = _local_datetime(day, first_in_time)
    last_out = _local_datetime(day, last_out_time)

    minutes_present = 0
    if first_in and last_out:
        minutes_present = max(0, int((last_out - first_in).total_seconds() // 60))

    minutes_late = 0
    minutes_early = 0
    calculated_status = AttendanceDailyRecord.ABSENT if first_in is None else AttendanceDailyRecord.PRESENT
    if policy and first_in and policy.expected_in:
        expected_in = _policy_datetime(day, policy.expected_in)
        late_threshold = expected_in + timedelta(minutes=policy.late_grace_minutes)
        if first_in > late_threshold:
            minutes_late = max(0, int((first_in - expected_in).total_seconds() // 60))
            calculated_status = AttendanceDailyRecord.LATE
    if policy and last_out and policy.expected_out:
        expected_out = _policy_datetime(day, policy.expected_out)
        early_threshold = expected_out - timedelta(minutes=policy.early_departure_grace_minutes)
        if last_out < early_threshold:
            minutes_early = max(0, int((expected_out - last_out).total_seconds() // 60))
            calculated_status = AttendanceDailyRecord.PARTIAL
    if policy and policy.minimum_presence_minutes and last_out and minutes_present < policy.minimum_presence_minutes:
        calculated_status = AttendanceDailyRecord.PARTIAL

    status = calculated_status if requested_status == ManualStaffAttendanceForm.AUTO else requested_status
    record.person_type = AttendanceIdentity.STAFF
    record.campus = staff.campus
    record.policy = policy
    record.status = status
    record.first_in = first_in
    record.last_out = last_out
    record.minutes_late = minutes_late
    record.minutes_early_departure = minutes_early
    record.minutes_present = minutes_present
    record.open_presence = bool(first_in and not last_out)
    record.manual_override = True
    record.note = note or ""
    record.save()
    AttendanceAdjustment.objects.create(
        record=record,
        before=before,
        after=_snapshot(record),
        reason=str(reason).strip(),
        changed_by=user,
    )
    return record


def _working_days(start: date, end: date, policy):
    day = start
    count = 0
    while day <= end:
        if policy:
            applies = policy.applies_on(day)
        else:
            applies = day.weekday() < 5
        count += int(applies)
        day += timedelta(days=1)
    return count


def _average_clock(datetimes):
    minute_values = []
    for value in datetimes:
        if not value:
            continue
        local_value = timezone.localtime(value)
        minute_values.append(local_value.hour * 60 + local_value.minute)
    if not minute_values:
        return "—"
    average = int(round(sum(minute_values) / len(minute_values)))
    hour, minute = divmod(average, 60)
    return f"{hour % 24:02d}:{minute:02d}"


@admin_portal_required
def attendance_dashboard(request):
    today = timezone.localdate()
    scoped = get_user_campus_scope(request.user)

    student_entries = AttendanceEntry.objects.filter(session__date=today)
    active_students = StudentProfile.objects.filter(is_active=True)
    active_staff = _staff_for(request.user)
    if scoped is not None:
        student_entries = student_entries.filter(session__offering__campus=scoped)
        active_students = active_students.filter(campus=scoped)

    staff_records = _staff_records_for(request.user).filter(date=today)
    devices = list(_devices_for(request.user).order_by("campus__name", "name"))

    staff_recorded = staff_records.values("staff_id").distinct().count()
    staff_present = staff_records.filter(
        status__in=[AttendanceDailyRecord.PRESENT, AttendanceDailyRecord.LATE, AttendanceDailyRecord.PARTIAL]
    ).count()

    return render(
        request,
        "portals/admin/attendance/dashboard.html",
        {
            "today": today,
            "active_student_total": active_students.count(),
            "student_roll_marks": student_entries.count(),
            "student_present_marks": student_entries.filter(status=AttendanceEntry.PRESENT).count(),
            "student_late_marks": student_entries.filter(status=AttendanceEntry.LATE).count(),
            "student_absent_marks": student_entries.filter(status=AttendanceEntry.ABSENT).count(),
            "active_staff_total": active_staff.count(),
            "staff_recorded": staff_recorded,
            "staff_present": staff_present,
            "staff_late": staff_records.filter(Q(status=AttendanceDailyRecord.LATE) | Q(minutes_late__gt=0)).count(),
            "staff_absent": staff_records.filter(status=AttendanceDailyRecord.ABSENT).count(),
            "staff_unrecorded": max(active_staff.count() - staff_recorded, 0),
            "recent_staff_records": staff_records.order_by("-updated_at")[:10],
            "device_total": len(devices),
            "device_online": sum(1 for item in devices if item.online),
            "devices": devices[:6],
        },
    )


@admin_portal_required
def staff_attendance(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get("start"), today.replace(day=1))
    end = _parse_date(request.GET.get("end"), today)
    if start > end:
        start, end = end, start

    q = (request.GET.get("q") or "").strip()
    scoped = get_user_campus_scope(request.user)
    campus_id = str(scoped.pk) if scoped is not None else (request.GET.get("campus") or "")

    staff_qs = _staff_for(request.user).order_by("last_name", "first_name")
    if campus_id:
        staff_qs = staff_qs.filter(campus_id=campus_id)
    if q:
        staff_qs = staff_qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(staff_id__icontains=q)
        )

    page_obj = Paginator(staff_qs, 50).get_page(request.GET.get("page") or 1)
    staff_page = list(page_obj.object_list)
    staff_ids = [item.pk for item in staff_page]
    records = list(
        _staff_records_for(request.user)
        .filter(staff_id__in=staff_ids, date__gte=start, date__lte=end)
        .order_by("staff_id", "date")
    )
    records_by_staff = defaultdict(list)
    for record in records:
        records_by_staff[record.staff_id].append(record)

    summaries = []
    for staff in staff_page:
        staff_records = records_by_staff.get(staff.pk, [])
        policy = resolve_policy(AttendanceIdentity.STAFF, staff.campus)
        expected_days = _working_days(start, end, policy)
        attended = [
            record
            for record in staff_records
            if record.status in {AttendanceDailyRecord.PRESENT, AttendanceDailyRecord.LATE, AttendanceDailyRecord.PARTIAL}
        ]
        absent = sum(record.status == AttendanceDailyRecord.ABSENT for record in staff_records)
        excused = sum(record.status == AttendanceDailyRecord.EXCUSED for record in staff_records)
        days_late = sum(bool(record.minutes_late) or record.status == AttendanceDailyRecord.LATE for record in staff_records)
        early_departures = sum(bool(record.minutes_early_departure) for record in staff_records)
        total_minutes = sum(record.minutes_present for record in staff_records)
        summaries.append(
            {
                "staff": staff,
                "expected_days": expected_days,
                "recorded_days": len(staff_records),
                "days_attended": len(attended),
                "days_absent": absent,
                "days_excused": excused,
                "days_late": days_late,
                "early_departures": early_departures,
                "attendance_rate": round((len(attended) / expected_days) * 100, 1) if expected_days else 0,
                "average_in": _average_clock([record.first_in for record in staff_records]),
                "average_out": _average_clock([record.last_out for record in staff_records]),
                "total_hours": f"{total_minutes // 60}h {total_minutes % 60:02d}m",
            }
        )

    query_string = f"start={start.isoformat()}&end={end.isoformat()}"
    if campus_id:
        query_string += f"&campus={campus_id}"
    if q:
        query_string += f"&q={q}"

    return render(
        request,
        "portals/admin/attendance/staff_list.html",
        {
            "summaries": summaries,
            "page_obj": page_obj,
            "start": start,
            "end": end,
            "q": q,
            "campus_id": campus_id,
            "campuses": _campuses_for(request.user),
            "query_string": query_string,
        },
    )


@admin_portal_required
def staff_attendance_manual(request):
    scoped = get_user_campus_scope(request.user)
    form = ManualStaffAttendanceForm(request.POST or None, campus_scope=scoped)
    if request.method == "POST" and form.is_valid():
        record = _save_manual_staff_record(
            staff=form.cleaned_data["staff"],
            day=form.cleaned_data["date"],
            requested_status=form.cleaned_data["status"],
            first_in_time=form.cleaned_data["first_in"],
            last_out_time=form.cleaned_data["last_out"],
            note=form.cleaned_data["note"],
            reason=form.cleaned_data["reason"],
            user=request.user,
        )
        messages.success(
            request,
            f"Staff attendance saved for {record.staff.get_full_name()} on {record.date:%d %b %Y}.",
        )
        target = reverse("admin_attendance_staff") + f"?start={record.date.isoformat()}&end={record.date.isoformat()}"
        return redirect(target)

    return render(
        request,
        "portals/admin/attendance/staff_manual.html",
        {"form": form},
    )
