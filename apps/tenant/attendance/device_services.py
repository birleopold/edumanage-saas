import csv
import hashlib
import io
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.tenant.academics.models import CourseOffering
from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Notification
from apps.tenant.parents.models import ParentStudentLink
from apps.tenant.students.models import StudentProfile

from .device_adapters import NormalizedDeviceEvent, adapter_for, parse_event_time
from .models import (
    AttendanceAdjustment,
    AttendanceDailyRecord,
    AttendanceDevice,
    AttendanceEntry,
    AttendanceEvent,
    AttendanceIdentity,
    AttendancePolicy,
    AttendanceSession,
)


def _tz(device: AttendanceDevice):
    try:
        return ZoneInfo(device.timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        return dt_timezone.utc


def _local_day_bounds(day, tz):
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)


def _event_day(event: AttendanceEvent):
    return event.occurred_at.astimezone(_tz(event.device)).date()


def resolve_policy(person_type: str, campus=None):
    qs = AttendancePolicy.objects.filter(person_type=person_type, is_active=True)
    if campus is not None:
        policy = qs.filter(campus=campus).order_by("-is_default", "id").first()
        if policy:
            return policy
    return qs.filter(campus__isnull=True).order_by("-is_default", "id").first()


def resolve_identity(
    device: AttendanceDevice,
    external_person_id: str,
    *,
    allow_system_id_fallback: bool = False,
    person_hint: str = "",
):
    person_id = str(external_person_id or "").strip()
    if not person_id:
        return None

    identity = AttendanceIdentity.objects.filter(
        namespace=device.identity_namespace,
        external_person_id=person_id,
        is_active=True,
    ).select_related("student", "staff").first()
    if identity:
        return identity

    allow_fallback = allow_system_id_fallback or bool((device.settings or {}).get("auto_match_system_ids"))
    if not allow_fallback:
        return None

    hint = str(person_hint or "").upper()
    students = StudentProfile.objects.filter(student_id=person_id, is_active=True)
    staff = StaffProfile.objects.filter(staff_id=person_id, is_active=True)
    if device.campus_id:
        students = students.filter(campus_id=device.campus_id)
        staff = staff.filter(campus_id=device.campus_id)
    student = students.first() if hint != AttendanceIdentity.STAFF else None
    staff_member = staff.first() if hint != AttendanceIdentity.STUDENT else None
    if bool(student) == bool(staff_member):
        return None

    identity = AttendanceIdentity(
        namespace=device.identity_namespace,
        external_person_id=person_id,
        person_type=AttendanceIdentity.STUDENT if student else AttendanceIdentity.STAFF,
        student=student,
        staff=staff_member,
        source="AUTO_ID_MATCH",
        is_active=True,
    )
    identity.full_clean()
    try:
        identity.save()
    except IntegrityError:
        identity = AttendanceIdentity.objects.filter(
            namespace=device.identity_namespace,
            external_person_id=person_id,
            is_active=True,
        ).select_related("student", "staff").first()
    return identity


def event_fingerprint(device: AttendanceDevice, event: NormalizedDeviceEvent) -> str:
    if event.external_event_id:
        raw = f"{device.code}|event|{event.external_event_id}"
    else:
        raw = "|".join(
            [
                device.code,
                event.external_person_id,
                event.occurred_at.astimezone(dt_timezone.utc).isoformat(timespec="seconds"),
                event.direction,
                event.event_code,
            ]
        )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _person_filter(identity: AttendanceIdentity):
    if identity.person_type == AttendanceIdentity.STUDENT:
        return {"student": identity.student, "staff": None}
    return {"staff": identity.staff, "student": None}


def _campus_for_identity(identity: AttendanceIdentity):
    target = identity.student if identity.student_id else identity.staff
    return getattr(target, "campus", None)


def _near_duplicate(event: AttendanceEvent, policy: AttendancePolicy | None):
    window = policy.duplicate_window_seconds if policy else 90
    if window <= 0:
        return False
    qs = AttendanceEvent.objects.filter(
        device=event.device,
        external_person_id=event.external_person_id,
        processing_status=AttendanceEvent.PROCESSED,
        occurred_at__gte=event.occurred_at - timedelta(seconds=window),
        occurred_at__lte=event.occurred_at + timedelta(seconds=window),
    ).exclude(pk=event.pk)
    if event.direction != AttendanceEvent.UNKNOWN:
        qs = qs.filter(direction=event.direction)
    return qs.exists()


def _accepted_event(event: AttendanceEvent, normalized: NormalizedDeviceEvent):
    if not normalized.counts_for_attendance:
        event.processing_status = AttendanceEvent.IGNORED
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "processed_at"])
        return False
    if not normalized.external_person_id:
        event.processing_status = AttendanceEvent.ERROR
        event.error_message = "The device event did not contain a person/user identifier."
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "error_message", "processed_at"])
        return False
    return True


def ingest_payload(
    *,
    device: AttendanceDevice,
    payload: dict,
    source: str = AttendanceEvent.PUSH,
    allow_system_id_fallback: bool = False,
):
    if not device.is_active:
        raise ValueError("Attendance device is disabled.")
    if not isinstance(payload, dict):
        raise ValueError("Attendance event must be an object/dictionary.")

    received_at = timezone.now()
    normalized = adapter_for(device).normalize(payload, device, received_at)
    occurred_at = normalized.occurred_at
    server_time_used = normalized.server_time_used

    settings = device.settings or {}
    if device.clock_offset_seconds and settings.get("apply_clock_offset", True) and not server_time_used:
        occurred_at = occurred_at - timedelta(seconds=device.clock_offset_seconds)

    max_future = int(settings.get("max_future_clock_skew_seconds", 300))
    if occurred_at > received_at + timedelta(seconds=max(0, max_future)):
        if settings.get("use_server_time_on_future_skew", True):
            occurred_at = received_at
            server_time_used = True

    normalized = NormalizedDeviceEvent(
        external_event_id=normalized.external_event_id,
        external_person_id=normalized.external_person_id,
        occurred_at=occurred_at,
        direction=normalized.direction,
        raw_direction=normalized.raw_direction,
        auth_method=normalized.auth_method,
        event_code=normalized.event_code,
        counts_for_attendance=normalized.counts_for_attendance,
        server_time_used=server_time_used,
    )
    fingerprint = event_fingerprint(device, normalized)
    existing = AttendanceEvent.objects.filter(event_hash=fingerprint).first()
    if existing:
        return existing, False

    identity = resolve_identity(
        device,
        normalized.external_person_id,
        allow_system_id_fallback=allow_system_id_fallback,
        person_hint=str(payload.get("person_type") or payload.get("person_kind") or ""),
    )
    person_fields = _person_filter(identity) if identity else {"student": None, "staff": None}
    skew_seconds = int((received_at - occurred_at).total_seconds()) if not server_time_used else 0

    try:
        with transaction.atomic():
            event = AttendanceEvent.objects.create(
                device=device,
                source=source,
                external_event_id=normalized.external_event_id,
                external_person_id=normalized.external_person_id,
                identity=identity,
                occurred_at=occurred_at,
                received_at=received_at,
                direction=normalized.direction,
                raw_direction=normalized.raw_direction,
                auth_method=normalized.auth_method,
                event_code=normalized.event_code,
                event_hash=fingerprint,
                raw_payload=payload,
                clock_skew_seconds=skew_seconds,
                server_time_used=server_time_used,
                **person_fields,
            )
    except IntegrityError:
        return AttendanceEvent.objects.get(event_hash=fingerprint), False

    device.last_seen_at = received_at
    device.last_event_at = occurred_at
    device.last_error = ""
    device.save(update_fields=["last_seen_at", "last_event_at", "last_error", "updated_at"])

    if not _accepted_event(event, normalized):
        return event, True

    if identity is None:
        event.processing_status = AttendanceEvent.UNMATCHED
        event.error_message = "No active identity mapping matched this device user ID."
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "error_message", "processed_at"])
        return event, True

    campus = _campus_for_identity(identity) or device.campus
    policy = resolve_policy(identity.person_type, campus)
    if _near_duplicate(event, policy):
        event.processing_status = AttendanceEvent.DUPLICATE
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_status", "processed_at"])
        return event, True

    event.processing_status = AttendanceEvent.PROCESSED
    event.error_message = ""
    event.processed_at = timezone.now()
    event.save(update_fields=["processing_status", "error_message", "processed_at"])
    record = reconcile_daily_record(event)
    _notify_for_event(event, record, policy)
    return event, True


def _processed_person_events(event: AttendanceEvent):
    day = _event_day(event)
    tz = _tz(event.device)
    start, end = _local_day_bounds(day, tz)
    qs = AttendanceEvent.objects.filter(
        processing_status=AttendanceEvent.PROCESSED,
        occurred_at__gte=start,
        occurred_at__lt=end,
    ).select_related("device")
    if event.student_id:
        qs = qs.filter(student_id=event.student_id)
    else:
        qs = qs.filter(staff_id=event.staff_id)
    return list(qs.order_by("occurred_at", "id"))


def _paired_presence(events, strategy):
    if not events:
        return None, None, 0, False
    times = [item.occurred_at for item in events]

    if strategy == AttendancePolicy.FIRST_LAST:
        first_in = times[0]
        last_out = times[-1] if len(times) > 1 else None
        minutes = max(0, int((last_out - first_in).total_seconds() // 60)) if last_out else 0
        return first_in, last_out, minutes, last_out is None

    open_at = None
    first_in = None
    last_out = None
    total_seconds = 0
    for index, item in enumerate(events):
        direction = item.direction
        if strategy == AttendancePolicy.ALTERNATE or direction == AttendanceEvent.UNKNOWN:
            direction = AttendanceEvent.IN if index % 2 == 0 else AttendanceEvent.OUT
        if direction in {AttendanceEvent.IN, AttendanceEvent.BREAK_IN}:
            if open_at is None:
                open_at = item.occurred_at
                if first_in is None:
                    first_in = open_at
        elif direction in {AttendanceEvent.OUT, AttendanceEvent.BREAK_OUT}:
            if open_at is not None and item.occurred_at >= open_at:
                total_seconds += (item.occurred_at - open_at).total_seconds()
                last_out = item.occurred_at
                open_at = None
            elif first_in is None:
                first_in = times[0]
                last_out = item.occurred_at
    if first_in is None:
        first_in = times[0]
    if last_out is None and len(times) > 1 and strategy == AttendancePolicy.DEVICE:
        unknowns = [e for e in events if e.direction == AttendanceEvent.UNKNOWN]
        if len(unknowns) == len(events):
            last_out = times[-1]
            total_seconds = (last_out - first_in).total_seconds()
            open_at = None
    return first_in, last_out, max(0, int(total_seconds // 60)), open_at is not None


def _combine_policy_time(day, value, tz):
    if value is None:
        return None
    return datetime.combine(day, value, tzinfo=tz).astimezone(dt_timezone.utc)


def reconcile_daily_record(event: AttendanceEvent, *, force=False):
    if not event.student_id and not event.staff_id:
        return None
    person_type = AttendanceIdentity.STUDENT if event.student_id else AttendanceIdentity.STAFF
    target = event.student if event.student_id else event.staff
    campus = getattr(target, "campus", None) or event.device.campus
    policy = resolve_policy(person_type, campus)
    day = _event_day(event)
    events = _processed_person_events(event)
    strategy = policy.direction_strategy if policy else AttendancePolicy.FIRST_LAST
    first_in, last_out, minutes_present, open_presence = _paired_presence(events, strategy)

    lookup = {"date": day, "student": event.student} if event.student_id else {"date": day, "staff": event.staff}
    defaults = {
        "person_type": person_type,
        "campus": campus,
        "policy": policy,
        "status": AttendanceDailyRecord.PRESENT,
    }
    record, _ = AttendanceDailyRecord.objects.get_or_create(defaults=defaults, **lookup)
    if record.manual_override and not force:
        record.source_event_count = len(events)
        record.save(update_fields=["source_event_count", "updated_at"])
        return record

    tz = _tz(event.device)
    expected_in = _combine_policy_time(day, policy.expected_in, tz) if policy else None
    expected_out = _combine_policy_time(day, policy.expected_out, tz) if policy else None
    minutes_late = 0
    minutes_early = 0
    status = AttendanceDailyRecord.PRESENT
    if expected_in and first_in:
        threshold = expected_in + timedelta(minutes=policy.late_grace_minutes)
        if first_in > threshold:
            minutes_late = max(0, int((first_in - expected_in).total_seconds() // 60))
            status = AttendanceDailyRecord.LATE
    if expected_out and last_out:
        threshold = expected_out - timedelta(minutes=policy.early_departure_grace_minutes)
        if last_out < threshold:
            minutes_early = max(0, int((expected_out - last_out).total_seconds() // 60))
            status = AttendanceDailyRecord.PARTIAL
    if policy and policy.minimum_presence_minutes and last_out and minutes_present < policy.minimum_presence_minutes:
        status = AttendanceDailyRecord.PARTIAL

    record.person_type = person_type
    record.campus = campus
    record.policy = policy
    record.status = status
    record.first_in = first_in
    record.last_out = last_out
    record.minutes_late = minutes_late
    record.minutes_early_departure = minutes_early
    record.minutes_present = minutes_present
    record.source_event_count = len(events)
    record.open_presence = open_presence
    record.save()
    return record


def _notify_for_event(event: AttendanceEvent, record: AttendanceDailyRecord | None, policy: AttendancePolicy | None):
    if not record or not policy or not event.student_id:
        return
    links = ParentStudentLink.objects.filter(student_id=event.student_id, parent__is_active=True).select_related("parent__user")
    if not links.exists():
        return
    day = record.date
    tz = _tz(event.device)
    local_time = event.occurred_at.astimezone(tz).strftime("%H:%M")
    student_name = event.student.get_full_name()

    is_first = record.first_in and abs((event.occurred_at - record.first_in).total_seconds()) < 1
    if policy.notify_parent_on_arrival and is_first and not AttendanceEvent.objects.filter(
        student_id=event.student_id,
        arrival_notified=True,
        occurred_at__date=event.occurred_at.date(),
    ).exclude(pk=event.pk).exists():
        for link in links:
            if link.parent.user_id:
                Notification.objects.create(
                    recipient=link.parent.user,
                    audience=Notification.PARENTS,
                    campus=record.campus,
                    title="Arrival recorded",
                    message=f"{student_name} was recorded at school at {local_time} on {day:%d %b %Y}.",
                    link="/parent/attendance/",
                )
        event.arrival_notified = True
        event.save(update_fields=["arrival_notified"])

    explicit_departure = event.direction in {AttendanceEvent.OUT, AttendanceEvent.BREAK_OUT}
    if policy.notify_parent_on_departure and explicit_departure and not AttendanceEvent.objects.filter(
        student_id=event.student_id,
        departure_notified=True,
        occurred_at__date=event.occurred_at.date(),
    ).exclude(pk=event.pk).exists():
        for link in links:
            if link.parent.user_id:
                Notification.objects.create(
                    recipient=link.parent.user,
                    audience=Notification.PARENTS,
                    campus=record.campus,
                    title="Departure recorded",
                    message=f"{student_name} was recorded leaving school at {local_time} on {day:%d %b %Y}.",
                    link="/parent/attendance/",
                )
        event.departure_notified = True
        event.save(update_fields=["departure_notified"])


def record_heartbeat(device: AttendanceDevice, payload: dict):
    now = timezone.now()
    device_time_value = payload.get("device_time") or payload.get("time") or payload.get("timestamp")
    if device_time_value:
        device_time, used_server = parse_event_time(device_time_value, device, now)
        if not used_server:
            device.clock_offset_seconds = int((device_time - now).total_seconds())
    capabilities = payload.get("capabilities")
    if isinstance(capabilities, dict):
        device.capabilities = {**(device.capabilities or {}), **capabilities}
    device.last_seen_at = now
    device.last_error = ""
    device.save(update_fields=["clock_offset_seconds", "capabilities", "last_seen_at", "last_error", "updated_at"])
    return device


def device_configuration(device: AttendanceDevice):
    policies = {}
    for person_type in (AttendanceIdentity.STUDENT, AttendanceIdentity.STAFF):
        policy = resolve_policy(person_type, device.campus)
        if policy:
            policies[person_type.lower()] = {
                "name": policy.name,
                "expected_in": policy.expected_in.isoformat() if policy.expected_in else None,
                "expected_out": policy.expected_out.isoformat() if policy.expected_out else None,
                "late_grace_minutes": policy.late_grace_minutes,
                "duplicate_window_seconds": policy.duplicate_window_seconds,
                "direction_strategy": policy.direction_strategy,
                "weekdays": policy.weekdays or [0, 1, 2, 3, 4],
            }
    return {
        "device": {
            "code": device.code,
            "vendor": device.vendor,
            "model": device.model_name,
            "timezone": device.timezone_name,
            "identity_namespace": device.identity_namespace,
            "connection_mode": device.connection_mode,
        },
        "policies": policies,
        "server_time": timezone.now().isoformat(),
    }


def reprocess_unmatched_identity(identity: AttendanceIdentity):
    events = AttendanceEvent.objects.filter(
        device__identity_namespace=identity.namespace,
        external_person_id=identity.external_person_id,
        processing_status=AttendanceEvent.UNMATCHED,
    ).select_related("device")
    processed = 0
    for event in events:
        event.identity = identity
        event.student = identity.student
        event.staff = identity.staff
        policy = resolve_policy(identity.person_type, _campus_for_identity(identity) or event.device.campus)
        if _near_duplicate(event, policy):
            event.processing_status = AttendanceEvent.DUPLICATE
        else:
            event.processing_status = AttendanceEvent.PROCESSED
            event.error_message = ""
            processed += 1
        event.processed_at = timezone.now()
        event.save(update_fields=["identity", "student", "staff", "processing_status", "error_message", "processed_at"])
        if event.processing_status == AttendanceEvent.PROCESSED:
            record = reconcile_daily_record(event)
            _notify_for_event(event, record, policy)
    return processed


def import_csv_events(*, device: AttendanceDevice, upload, allow_system_id_fallback=False):
    raw = upload.read()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = str(raw)
    reader = csv.DictReader(io.StringIO(text))
    summary = {"rows": 0, "processed": 0, "duplicates": 0, "unmatched": 0, "ignored": 0, "errors": 0}
    for row in reader:
        summary["rows"] += 1
        try:
            event, _ = ingest_payload(
                device=device,
                payload=dict(row),
                source=AttendanceEvent.FILE,
                allow_system_id_fallback=allow_system_id_fallback,
            )
            if event.processing_status == AttendanceEvent.PROCESSED:
                summary["processed"] += 1
            elif event.processing_status == AttendanceEvent.DUPLICATE:
                summary["duplicates"] += 1
            elif event.processing_status == AttendanceEvent.UNMATCHED:
                summary["unmatched"] += 1
            elif event.processing_status == AttendanceEvent.IGNORED:
                summary["ignored"] += 1
            elif event.processing_status == AttendanceEvent.ERROR:
                summary["errors"] += 1
        except Exception:
            summary["errors"] += 1
    return summary


def finalize_absences(*, day, campus, person_type):
    policy = resolve_policy(person_type, campus)
    if not policy or not policy.applies_on(day):
        return {"created": 0, "skipped": True, "reason": "No active attendance policy applies on this date."}
    created = 0
    if person_type == AttendanceIdentity.STUDENT:
        people = StudentProfile.objects.filter(campus=campus, is_active=True)
        for student in people.iterator():
            _, was_created = AttendanceDailyRecord.objects.get_or_create(
                date=day,
                student=student,
                defaults={
                    "person_type": person_type,
                    "campus": campus,
                    "policy": policy,
                    "status": AttendanceDailyRecord.ABSENT,
                },
            )
            created += int(was_created)
    else:
        people = StaffProfile.objects.filter(campus=campus, is_active=True)
        for staff in people.iterator():
            _, was_created = AttendanceDailyRecord.objects.get_or_create(
                date=day,
                staff=staff,
                defaults={
                    "person_type": person_type,
                    "campus": campus,
                    "policy": policy,
                    "status": AttendanceDailyRecord.ABSENT,
                },
            )
            created += int(was_created)
    return {"created": created, "skipped": False, "reason": ""}


def _record_snapshot(record: AttendanceDailyRecord):
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


def apply_manual_adjustment(*, record, status, first_in, last_out, note, reason, user):
    if not str(reason or "").strip():
        raise ValueError("A reason is required for a manual attendance correction.")
    before = _record_snapshot(record)
    record.status = status
    record.first_in = first_in
    record.last_out = last_out
    record.note = note or ""
    record.manual_override = True
    if first_in and last_out and last_out >= first_in:
        record.minutes_present = int((last_out - first_in).total_seconds() // 60)
        record.open_presence = False
    elif first_in:
        record.open_presence = True
    record.save()
    AttendanceAdjustment.objects.create(
        record=record,
        before=before,
        after=_record_snapshot(record),
        reason=str(reason).strip(),
        changed_by=user,
    )
    return record


def clear_manual_adjustment(*, record, reason, user):
    if not str(reason or "").strip():
        raise ValueError("A reason is required to clear a manual override.")
    before = _record_snapshot(record)
    record.manual_override = False
    record.save(update_fields=["manual_override", "updated_at"])
    event = AttendanceEvent.objects.filter(
        student=record.student if record.student_id else None,
        staff=record.staff if record.staff_id else None,
        processing_status=AttendanceEvent.PROCESSED,
    ).order_by("-occurred_at").first()
    if event:
        reconcile_daily_record(event, force=True)
        record.refresh_from_db()
    AttendanceAdjustment.objects.create(
        record=record,
        before=before,
        after=_record_snapshot(record),
        reason=str(reason).strip(),
        changed_by=user,
    )
    return record


def materialize_legacy_class_attendance(*, event: AttendanceEvent, offering_id, status=None):
    if not event.student_id or not offering_id:
        return None
    offering = CourseOffering.objects.filter(pk=offering_id).first()
    if not offering:
        return None
    session, _ = AttendanceSession.objects.get_or_create(
        offering=offering,
        date=_event_day(event),
        defaults={"taken_by": offering.teacher},
    )
    entry_status = status or AttendanceEntry.PRESENT
    entry, _ = AttendanceEntry.objects.update_or_create(
        session=session,
        student=event.student,
        defaults={"status": entry_status},
    )
    return entry
