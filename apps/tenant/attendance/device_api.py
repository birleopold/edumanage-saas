from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .device_services import device_configuration, ingest_payload, record_heartbeat
from .models import AttendanceDevice, AttendanceEvent


MAX_BATCH_EVENTS = 500
MAX_REQUEST_BYTES = 5 * 1024 * 1024


def _plain_data(data):
    if hasattr(data, "dict"):
        return data.dict()
    return data


def _request_too_large(request):
    raw = request.META.get("CONTENT_LENGTH")
    if not raw:
        return False
    try:
        return int(raw) > MAX_REQUEST_BYTES
    except (TypeError, ValueError):
        return False


def _raw_device_token(request):
    direct = (request.headers.get("X-Device-Key") or request.headers.get("X-Attendance-Key") or "").strip()
    if direct:
        return direct
    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("device "):
        return authorization.split(" ", 1)[1].strip()
    return ""


def _device_code(request, payload=None):
    payload = payload if isinstance(payload, dict) else {}
    return str(
        request.headers.get("X-Device-Code")
        or request.headers.get("X-Attendance-Device")
        or payload.get("device_code")
        or payload.get("device")
        or payload.get("serial")
        or payload.get("SN")
        or ""
    ).strip()


def _client_ip(request):
    # REMOTE_ADDR is intentionally used instead of trusting arbitrary X-Forwarded-For.
    return str(request.META.get("REMOTE_ADDR") or "").strip()


def authenticate_device(request, payload=None):
    code = _device_code(request, payload)
    if not code:
        return None, "Device code is required."
    device = AttendanceDevice.objects.filter(code=code, is_active=True).select_related("campus").first()
    if not device:
        return None, "Unknown or disabled attendance device."
    if not device.verify_token(_raw_device_token(request)):
        return None, "Invalid device key."
    allowed_ips = (device.settings or {}).get("allowed_ips") or []
    if allowed_ips and _client_ip(request) not in {str(ip).strip() for ip in allowed_ips}:
        return None, "This device connection is not allowed from the current IP address."
    return device, ""


def _source_for_device(device: AttendanceDevice):
    return {
        AttendanceDevice.PUSH: AttendanceEvent.PUSH,
        AttendanceDevice.PULL: AttendanceEvent.PULL,
        AttendanceDevice.EDGE: AttendanceEvent.EDGE,
        AttendanceDevice.FILE: AttendanceEvent.FILE,
    }.get(device.connection_mode, AttendanceEvent.PUSH)


class AttendanceDeviceEvents(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if _request_too_large(request):
            return Response(
                {"detail": f"Attendance device requests must be {MAX_REQUEST_BYTES // (1024 * 1024)} MB or smaller."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        body = _plain_data(request.data)
        if not isinstance(body, dict):
            return Response({"detail": "Request body must be an object."}, status=status.HTTP_400_BAD_REQUEST)
        device, error = authenticate_device(request, body)
        if not device:
            return Response({"detail": error}, status=status.HTTP_401_UNAUTHORIZED)

        events = body.get("events")
        if events is None:
            events = [body]
        if not isinstance(events, list):
            return Response({"detail": "events must be a list."}, status=status.HTTP_400_BAD_REQUEST)
        if len(events) > MAX_BATCH_EVENTS:
            return Response(
                {"detail": f"A maximum of {MAX_BATCH_EVENTS} events may be sent in one batch."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        source = _source_for_device(device)
        results = []
        counts = {"processed": 0, "duplicates": 0, "unmatched": 0, "ignored": 0, "errors": 0}
        for raw_event in events:
            if not isinstance(raw_event, dict):
                counts["errors"] += 1
                results.append({"id": None, "status": AttendanceEvent.ERROR, "error": "Event is not an object."})
                continue
            payload = {**raw_event}
            payload.setdefault("device_code", device.code)
            try:
                item, created = ingest_payload(device=device, payload=payload, source=source)
                key = {
                    AttendanceEvent.PROCESSED: "processed",
                    AttendanceEvent.DUPLICATE: "duplicates",
                    AttendanceEvent.UNMATCHED: "unmatched",
                    AttendanceEvent.IGNORED: "ignored",
                    AttendanceEvent.ERROR: "errors",
                }.get(item.processing_status)
                if key:
                    counts[key] += 1
                results.append(
                    {
                        "id": item.id,
                        "status": item.processing_status,
                        "created": created,
                        "person_id": item.external_person_id,
                        "occurred_at": item.occurred_at.isoformat(),
                        "error": item.error_message,
                    }
                )
            except Exception as exc:
                device.last_error = str(exc)[:1000]
                device.save(update_fields=["last_error", "updated_at"])
                counts["errors"] += 1
                public_error = str(exc) if isinstance(exc, ValueError) else "Unable to process attendance event."
                results.append({"id": None, "status": AttendanceEvent.ERROR, "error": public_error})

        return Response({"device": device.code, "received": len(events), **counts, "results": results})


class AttendanceDeviceHeartbeat(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if _request_too_large(request):
            return Response(
                {"detail": f"Attendance device requests must be {MAX_REQUEST_BYTES // (1024 * 1024)} MB or smaller."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        body = _plain_data(request.data)
        if not isinstance(body, dict):
            body = {}
        device, error = authenticate_device(request, body)
        if not device:
            return Response({"detail": error}, status=status.HTTP_401_UNAUTHORIZED)
        record_heartbeat(device, body)
        return Response(
            {
                "device": device.code,
                "ok": True,
                "server_time": timezone.now().isoformat(),
                "clock_offset_seconds": device.clock_offset_seconds,
            }
        )


class AttendanceDeviceConfiguration(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        device, error = authenticate_device(request, {})
        if not device:
            return Response({"detail": error}, status=status.HTTP_401_UNAUTHORIZED)
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at", "updated_at"])
        return Response(device_configuration(device))
