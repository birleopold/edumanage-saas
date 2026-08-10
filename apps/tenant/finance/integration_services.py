import json
import urllib.parse
import urllib.request
from decimal import Decimal

from django.utils import timezone

from apps.tenant.academics.models import CourseOffering
from apps.tenant.attendance.models import AttendanceDevice, AttendanceEntry, AttendanceEvent
from apps.tenant.students.models import StudentProfile
from apps.tenant.transport.models import Vehicle, VehicleTracking

from .models import BiometricAttendanceEvent, BiometricDevice, IntegrationEventLog, IntegrationProviderConfig, MeetingSessionLink, SSOLoginProvider
from .payment_gateway import initiate_collection, process_gateway_callback
from .communication_providers import send_email_notice, send_fee_message_provider


def log_event(event_type, status, payload=None, response=None, provider=None, api_key=None, error="", reference=""):
    return IntegrationEventLog.objects.create(event_type=event_type, status=status, request_payload=payload or {}, response_payload=response or {}, provider=provider, api_key=api_key, error_message=error, external_reference=reference)


def process_biometric_event(payload, api_key=None):
    """Compatibility bridge for the original biometric integration endpoint.

    New attendance hardware should use ``/api/v1/attendance/devices/events/``.
    This function deliberately keeps the old scoped-API endpoint working while
    routing its punches through the universal attendance event ledger. A class
    attendance entry is only materialized when ``offering_id`` is explicitly
    supplied; otherwise the event represents campus/staff presence only.
    """

    from apps.tenant.attendance.device_services import ingest_payload, materialize_legacy_class_attendance

    payload = dict(payload or {})
    device_code = str(payload.get("device_code") or payload.get("device") or "").strip()
    person_id = str(
        payload.get("person_id")
        or payload.get("student_id")
        or payload.get("staff_id")
        or payload.get("external_person_id")
        or ""
    ).strip()
    offering_id = payload.get("offering_id")
    class_status = payload.get("status") or AttendanceEntry.PRESENT

    legacy_device = BiometricDevice.objects.filter(device_code=device_code, is_active=True).first() if device_code else None
    if legacy_device:
        legacy_device.last_seen_at = timezone.now()
        legacy_device.save(update_fields=["last_seen_at"])

    canonical_code = device_code or "LEGACY-BIOMETRIC-API"
    namespace = f"legacy-biometric-{legacy_device.pk}" if legacy_device else "legacy-biometric"
    universal_device, created = AttendanceDevice.objects.get_or_create(
        code=canonical_code,
        defaults={
            "name": legacy_device.name if legacy_device else "Legacy biometric API",
            "serial_number": device_code,
            "vendor": AttendanceDevice.GENERIC,
            "campus": legacy_device.campus if legacy_device else None,
            "connection_mode": AttendanceDevice.PUSH,
            "protocol": "legacy-scoped-api",
            "identity_namespace": namespace,
            "settings": {"auto_match_system_ids": True},
            "is_active": True,
        },
    )
    if not created:
        changed = []
        if legacy_device and not universal_device.campus_id and legacy_device.campus_id:
            universal_device.campus = legacy_device.campus
            changed.append("campus")
        if not universal_device.protocol:
            universal_device.protocol = "legacy-scoped-api"
            changed.append("protocol")
        if changed:
            changed.append("updated_at")
            universal_device.save(update_fields=changed)

    payload.setdefault("device_code", universal_device.code)
    if person_id:
        payload.setdefault("person_id", person_id)

    universal_event, _ = ingest_payload(
        device=universal_device,
        payload=payload,
        source=AttendanceEvent.LEGACY,
        allow_system_id_fallback=True,
    )

    offering = CourseOffering.objects.filter(pk=offering_id).first() if offering_id else None
    entry = None
    if universal_event.student_id and offering is not None and universal_event.processing_status in {
        AttendanceEvent.PROCESSED,
        AttendanceEvent.DUPLICATE,
    }:
        entry = materialize_legacy_class_attendance(
            event=universal_event,
            offering_id=offering.pk,
            status=class_status,
        )

    legacy_event = BiometricAttendanceEvent.objects.create(
        device=legacy_device,
        student=universal_event.student,
        external_person_id=person_id,
        event_time=universal_event.occurred_at,
        offering=offering,
        attendance_entry=entry,
        raw_payload=payload,
        processed=universal_event.processing_status in {AttendanceEvent.PROCESSED, AttendanceEvent.DUPLICATE},
        error_message=universal_event.error_message,
    )

    ok = legacy_event.processed
    log_event(
        "biometric.attendance",
        "SUCCESS" if ok else "FAILED",
        payload,
        {
            "legacy_event_id": legacy_event.id,
            "universal_event_id": universal_event.id,
            "attendance_entry_id": entry.id if entry else None,
            "processing_status": universal_event.processing_status,
        },
        provider=legacy_device.provider if legacy_device else None,
        api_key=api_key,
        error="" if ok else universal_event.error_message,
        reference=person_id,
    )
    return legacy_event


def record_vehicle_gps(payload, api_key=None):
    device_id = str(payload.get("device_id") or payload.get("gps_device_id") or "")
    vehicle = Vehicle.objects.filter(gps_device_id=device_id).first() or Vehicle.objects.filter(plate_number=payload.get("plate_number") or "").first()
    if not vehicle:
        log_event("transport.gps", "FAILED", payload, api_key=api_key, error="Vehicle not found", reference=device_id)
        raise ValueError("Vehicle not found.")
    item = VehicleTracking.objects.create(vehicle=vehicle, latitude=Decimal(str(payload.get("latitude"))), longitude=Decimal(str(payload.get("longitude"))), speed=Decimal(str(payload.get("speed"))) if payload.get("speed") is not None else None, heading=payload.get("heading"), is_moving=bool(payload.get("is_moving", True)))
    log_event("transport.gps", "SUCCESS", payload, {"tracking_id": item.id}, api_key=api_key, reference=device_id)
    return item


def create_meeting_link(*, provider_type, title, offering=None, starts_at=None, ends_at=None, created_by=None):
    provider = IntegrationProviderConfig.objects.filter(provider_type=provider_type, is_active=True).first()
    if not provider:
        raise ValueError("Meeting provider is not configured.")
    url_template = provider.settings.get("meeting_url_template") or provider.base_url
    if not url_template:
        raise ValueError("Meeting URL template/base URL is missing.")
    meeting_id = f"EDU-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    meeting_url = url_template.format(meeting_id=meeting_id, title=urllib.parse.quote(title)) if "{" in url_template else url_template
    item = MeetingSessionLink.objects.create(provider_type=provider_type, provider=provider, offering=offering, title=title, meeting_url=meeting_url, external_meeting_id=meeting_id, starts_at=starts_at, ends_at=ends_at, created_by=created_by)
    log_event("meeting.create", "SUCCESS", {"title": title}, {"meeting_url": meeting_url}, provider=provider)
    return item


def sso_authorization_url(provider_type, redirect_uri, state):
    provider = SSOLoginProvider.objects.filter(provider_type=provider_type, is_active=True).first()
    if not provider:
        raise ValueError("SSO provider not configured.")
    query = urllib.parse.urlencode({"client_id": provider.client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": provider.scopes, "state": state})
    return f"{provider.authorization_url}?{query}"


def provider_readiness_summary():
    active = IntegrationProviderConfig.objects.filter(is_active=True)
    return {"providers": active.count(), "biometric": active.filter(provider_type=IntegrationProviderConfig.BIOMETRIC).exists(), "sms": active.filter(provider_type=IntegrationProviderConfig.SMS).exists(), "whatsapp": active.filter(provider_type=IntegrationProviderConfig.WHATSAPP).exists(), "email": active.filter(provider_type=IntegrationProviderConfig.EMAIL).exists(), "mtn_momo": active.filter(provider_type=IntegrationProviderConfig.MTN_MOMO).exists(), "airtel_money": active.filter(provider_type=IntegrationProviderConfig.AIRTEL_MONEY).exists(), "gps": active.filter(provider_type=IntegrationProviderConfig.GPS).exists(), "meetings": active.filter(provider_type__in=[IntegrationProviderConfig.GOOGLE_MEET, IntegrationProviderConfig.ZOOM, IntegrationProviderConfig.BIGBLUEBUTTON]).count()}
