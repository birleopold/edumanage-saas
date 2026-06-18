import json
import urllib.parse
import urllib.request
from decimal import Decimal

from django.utils import timezone

from apps.tenant.academics.models import CourseOffering
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.students.models import StudentProfile
from apps.tenant.transport.models import Vehicle, VehicleTracking

from .models import BiometricAttendanceEvent, BiometricDevice, IntegrationEventLog, IntegrationProviderConfig, MeetingSessionLink, SSOLoginProvider
from .payment_gateway import initiate_collection, process_gateway_callback
from .communication_providers import send_email_notice, send_fee_message_provider


def log_event(event_type, status, payload=None, response=None, provider=None, api_key=None, error="", reference=""):
    return IntegrationEventLog.objects.create(event_type=event_type, status=status, request_payload=payload or {}, response_payload=response or {}, provider=provider, api_key=api_key, error_message=error, external_reference=reference)


def process_biometric_event(payload, api_key=None):
    device_code = str(payload.get("device_code") or payload.get("device") or "")
    person_id = str(payload.get("person_id") or payload.get("student_id") or payload.get("external_person_id") or "")
    offering_id = payload.get("offering_id")
    status = payload.get("status") or AttendanceEntry.PRESENT
    device = BiometricDevice.objects.filter(device_code=device_code, is_active=True).first()
    if device:
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])
    student = None
    if person_id:
        student = StudentProfile.objects.filter(student_id=person_id).first() or StudentProfile.objects.filter(id=person_id).first()
    offering = CourseOffering.objects.filter(pk=offering_id).first() if offering_id else None
    event = BiometricAttendanceEvent.objects.create(device=device, student=student, external_person_id=person_id, offering=offering, raw_payload=payload)
    if not student or not offering:
        event.error_message = "Student or offering not found."
        event.save(update_fields=["error_message"])
        log_event("biometric.attendance", "FAILED", payload, provider=device.provider if device else None, api_key=api_key, error=event.error_message, reference=person_id)
        return event
    session, _ = AttendanceSession.objects.get_or_create(offering=offering, date=timezone.localdate(), defaults={"taken_by": offering.teacher})
    entry, _ = AttendanceEntry.objects.update_or_create(session=session, student=student, defaults={"status": status})
    event.attendance_entry = entry
    event.processed = True
    event.save(update_fields=["attendance_entry", "processed"])
    log_event("biometric.attendance", "SUCCESS", payload, {"entry_id": entry.id}, provider=device.provider if device else None, api_key=api_key, reference=person_id)
    return event


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
