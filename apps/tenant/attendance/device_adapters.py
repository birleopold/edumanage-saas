"""Vendor adapters for attendance hardware.

Adapters translate vendor payloads into EduManage's canonical event shape. They do
not make academic decisions; policy evaluation happens in device_services.py.
"""

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import AttendanceDevice, AttendanceEvent


@dataclass(frozen=True)
class NormalizedDeviceEvent:
    external_event_id: str
    external_person_id: str
    occurred_at: datetime
    direction: str = AttendanceEvent.UNKNOWN
    raw_direction: str = ""
    auth_method: str = AttendanceEvent.AUTH_UNKNOWN
    event_code: str = ""
    counts_for_attendance: bool = True
    server_time_used: bool = False


def _first(payload: dict, *keys: str, default=None):
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return default


def _nested(payload: dict, path: str, default=None):
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def _device_tz(device: AttendanceDevice):
    try:
        return ZoneInfo(device.timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        return dt_timezone.utc


def parse_event_time(value, device: AttendanceDevice, fallback: datetime) -> tuple[datetime, bool]:
    if value in (None, ""):
        return fallback, True

    tz = _device_tz(device)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 10_000_000_000:  # milliseconds
            numeric /= 1000.0
        parsed = datetime.fromtimestamp(numeric, tz=dt_timezone.utc)
    else:
        raw = str(value).strip()
        if raw.isdigit():
            numeric = float(raw)
            if numeric > 10_000_000_000:
                numeric /= 1000.0
            parsed = datetime.fromtimestamp(numeric, tz=dt_timezone.utc)
        else:
            parsed = None
            candidates = [raw]
            if raw.endswith("Z"):
                candidates.insert(0, raw[:-1] + "+00:00")
            for candidate in candidates:
                try:
                    parsed = datetime.fromisoformat(candidate)
                    break
                except ValueError:
                    continue
            if parsed is None:
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                ):
                    try:
                        parsed = datetime.strptime(raw, fmt)
                        break
                    except ValueError:
                        continue
            if parsed is None:
                return fallback, True

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(dt_timezone.utc), False


def normalize_direction(value, device: AttendanceDevice) -> tuple[str, str]:
    raw = "" if value is None else str(value).strip()
    configured = (device.settings or {}).get("direction_map") or {}
    if raw in configured:
        value = configured[raw]
    fixed = str((device.settings or {}).get("fixed_direction") or "").upper()
    if fixed in {AttendanceEvent.IN, AttendanceEvent.OUT, AttendanceEvent.BREAK_IN, AttendanceEvent.BREAK_OUT}:
        return fixed, raw

    normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "IN": AttendanceEvent.IN,
        "ENTRY": AttendanceEvent.IN,
        "ENTER": AttendanceEvent.IN,
        "CHECKIN": AttendanceEvent.IN,
        "CHECK_IN": AttendanceEvent.IN,
        "CLOCK_IN": AttendanceEvent.IN,
        "OUT": AttendanceEvent.OUT,
        "EXIT": AttendanceEvent.OUT,
        "LEAVE": AttendanceEvent.OUT,
        "CHECKOUT": AttendanceEvent.OUT,
        "CHECK_OUT": AttendanceEvent.OUT,
        "CLOCK_OUT": AttendanceEvent.OUT,
        "BREAK_OUT": AttendanceEvent.BREAK_OUT,
        "BREAKOUT": AttendanceEvent.BREAK_OUT,
        "BREAK_IN": AttendanceEvent.BREAK_IN,
        "BREAKIN": AttendanceEvent.BREAK_IN,
    }
    return aliases.get(normalized, AttendanceEvent.UNKNOWN), raw


def normalize_auth(value) -> str:
    normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if "FACE" in normalized:
        return AttendanceEvent.FACE
    if "FINGER" in normalized or normalized in {"FP", "FINGERPRINT"}:
        return AttendanceEvent.FINGERPRINT
    if "PALM" in normalized:
        return AttendanceEvent.PALM
    if "QR" in normalized:
        return AttendanceEvent.QR
    if "CARD" in normalized or "RFID" in normalized or "MIFARE" in normalized:
        return AttendanceEvent.RFID
    if "PIN" in normalized or "PASSWORD" in normalized:
        return AttendanceEvent.PIN
    if "MOBILE" in normalized or "APP" in normalized:
        return AttendanceEvent.MOBILE
    return AttendanceEvent.AUTH_UNKNOWN


class BaseAdapter:
    def normalize(self, payload: dict, device: AttendanceDevice, received_at: datetime) -> NormalizedDeviceEvent:
        raise NotImplementedError


class GenericJSONAdapter(BaseAdapter):
    def normalize(self, payload: dict, device: AttendanceDevice, received_at: datetime) -> NormalizedDeviceEvent:
        person_id = _first(
            payload,
            "person_id",
            "external_person_id",
            "biometric_user_id",
            "user_id",
            "student_id",
            "staff_id",
            "employee_id",
            "pin",
            default="",
        )
        event_id = _first(payload, "event_id", "external_event_id", "transaction_id", "log_id", "id", default="")
        raw_time = _first(payload, "timestamp", "event_time", "occurred_at", "time", "datetime", "date_time")
        occurred_at, server_time_used = parse_event_time(raw_time, device, received_at)
        direction, raw_direction = normalize_direction(
            _first(payload, "direction", "in_out", "punch_state", "attendance_status", "state"),
            device,
        )
        auth = normalize_auth(_first(payload, "auth_method", "verify_mode", "verification", "credential_type"))
        event_code = str(_first(payload, "event_code", "event_type", "type", default="") or "")
        accepted_codes = [str(x) for x in ((device.settings or {}).get("accepted_event_codes") or [])]
        counts = not accepted_codes or event_code in accepted_codes
        return NormalizedDeviceEvent(
            external_event_id=str(event_id or ""),
            external_person_id=str(person_id or "").strip(),
            occurred_at=occurred_at,
            direction=direction,
            raw_direction=raw_direction,
            auth_method=auth,
            event_code=event_code,
            counts_for_attendance=counts,
            server_time_used=server_time_used,
        )


class ZKTecoAdapter(GenericJSONAdapter):
    """Flexible parser for ZKTeco PUSH/ADMS or middleware-normalized payloads.

    ZKTeco deployments vary by firmware and PUSH SDK generation, so the adapter
    intentionally accepts common aliases and allows exact direction/event maps
    to be configured per device in ``settings``.
    """

    def normalize(self, payload: dict, device: AttendanceDevice, received_at: datetime) -> NormalizedDeviceEvent:
        canonical = dict(payload)
        canonical.setdefault("person_id", _first(payload, "PIN", "Pin", "pin", "UserID", "userId", "user_id"))
        canonical.setdefault("event_id", _first(payload, "ID", "log_id", "transaction_id"))
        canonical.setdefault("timestamp", _first(payload, "Time", "time", "verify_time", "event_time", "timestamp"))
        canonical.setdefault("direction", _first(payload, "punch_state", "PunchState", "in_out", "state", "attendance_status"))
        canonical.setdefault("auth_method", _first(payload, "VerifyMode", "verify_mode", "verify", "verification"))
        canonical.setdefault("event_code", _first(payload, "event_code", "type", "table"))
        return super().normalize(canonical, device, received_at)


class HikvisionAdapter(GenericJSONAdapter):
    """Parser for Hikvision ISAPI/access-controller event JSON and middleware payloads."""

    def normalize(self, payload: dict, device: AttendanceDevice, received_at: datetime) -> NormalizedDeviceEvent:
        event = payload.get("AccessControllerEvent") or payload.get("AcsEvent") or payload.get("event") or {}
        if not isinstance(event, dict):
            event = {}
        canonical = dict(payload)
        canonical["person_id"] = (
            event.get("employeeNoString")
            or event.get("employeeNo")
            or event.get("personId")
            or payload.get("employeeNoString")
            or event.get("cardNo")
            or payload.get("cardNo")
        )
        canonical["event_id"] = event.get("serialNo") or payload.get("serialNo") or payload.get("event_id")
        canonical["timestamp"] = payload.get("dateTime") or event.get("dateTime") or payload.get("timestamp")
        canonical["direction"] = event.get("attendanceStatus") or payload.get("attendanceStatus") or event.get("direction")
        canonical["auth_method"] = event.get("currentVerifyMode") or payload.get("currentVerifyMode") or event.get("verifyMode")
        major = event.get("major") or payload.get("major") or ""
        minor = event.get("minor") or payload.get("minor") or ""
        canonical["event_code"] = f"{major}:{minor}" if major or minor else payload.get("eventType") or ""
        return super().normalize(canonical, device, received_at)


class SupremaAdapter(GenericJSONAdapter):
    """Parser for BioStar 2/G-SDK event log objects."""

    SUCCESS_EVENT_CODES = {0x1000, 0x1300}
    FAILURE_EVENT_CODES = {0x1100}

    def normalize(self, payload: dict, device: AttendanceDevice, received_at: datetime) -> NormalizedDeviceEvent:
        canonical = dict(payload)
        canonical["person_id"] = _first(payload, "userID", "user_id", "person_id")
        canonical["event_id"] = _first(payload, "ID", "id", "event_id")
        canonical["timestamp"] = _first(payload, "timestamp", "datetime", "event_time")
        canonical["direction"] = _first(payload, "TNAKey", "tna_key", "direction")
        event_code = _first(payload, "eventCode", "event_code", default="")
        canonical["event_code"] = event_code
        canonical["auth_method"] = _first(payload, "credential", "auth_method", "subCode")
        normalized = super().normalize(canonical, device, received_at)
        counts = normalized.counts_for_attendance
        try:
            numeric_code = int(str(event_code), 0) if isinstance(event_code, str) else int(event_code)
        except (TypeError, ValueError):
            numeric_code = None
        if numeric_code in self.FAILURE_EVENT_CODES:
            counts = False
        elif numeric_code in self.SUCCESS_EVENT_CODES:
            counts = True
        return NormalizedDeviceEvent(
            external_event_id=normalized.external_event_id,
            external_person_id=normalized.external_person_id,
            occurred_at=normalized.occurred_at,
            direction=normalized.direction,
            raw_direction=normalized.raw_direction,
            auth_method=normalized.auth_method,
            event_code=normalized.event_code,
            counts_for_attendance=counts,
            server_time_used=normalized.server_time_used,
        )


def adapter_for(device: AttendanceDevice) -> BaseAdapter:
    if device.vendor == AttendanceDevice.ZKTECO:
        return ZKTecoAdapter()
    if device.vendor == AttendanceDevice.HIKVISION:
        return HikvisionAdapter()
    if device.vendor == AttendanceDevice.SUPREMA:
        return SupremaAdapter()
    return GenericJSONAdapter()
