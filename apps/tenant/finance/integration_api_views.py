import uuid

from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework.views import APIView

from .integration_security import HasScopedIntegrationKey
from .integration_services import create_meeting_link, process_biometric_event, provider_readiness_summary, record_vehicle_gps, sso_authorization_url
from .models import IntegrationEventLog, IntegrationProviderConfig, MeetingSessionLink, SSOLoginProvider
from .payment_gateway import process_gateway_callback
from .payment_gateway_models import PaymentGatewayEvent


class IntegrationReadiness(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "integrations-admin"

    def get(self, request):
        return Response(provider_readiness_summary())


class BiometricAttendanceIngest(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "attendance-write"

    def post(self, request):
        event = process_biometric_event(request.data, api_key=request.integration_api_key)
        return Response({"id": event.id, "processed": event.processed, "error": event.error_message})


class VehicleGPSIngest(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "transport-gps"

    def post(self, request):
        item = record_vehicle_gps(request.data, api_key=request.integration_api_key)
        return Response({"id": item.id, "vehicle_id": item.vehicle_id, "timestamp": item.timestamp})


class MeetingCreate(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "meetings-write"

    def post(self, request):
        link = create_meeting_link(provider_type=request.data.get("provider_type") or MeetingSessionLink.ZOOM, title=request.data.get("title") or "Online lesson", offering_id=request.data.get("offering_id"), starts_at=request.data.get("starts_at"), ends_at=request.data.get("ends_at"))
        return Response({"id": link.id, "meeting_url": link.meeting_url, "provider_type": link.provider_type})


class IntegrationEvents(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "integrations-admin"

    def get(self, request):
        rows = IntegrationEventLog.objects.order_by("-created_at")[:100]
        return Response({"results": [{"id": r.id, "event_type": r.event_type, "status": r.status, "external_reference": r.external_reference, "error_message": r.error_message, "created_at": r.created_at} for r in rows]})


def sso_start(request, provider_type):
    state = uuid.uuid4().hex
    request.session["sso_state"] = state
    redirect_uri = request.build_absolute_uri("/sso/callback/")
    try:
        return redirect(sso_authorization_url(provider_type.upper(), redirect_uri, state))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


def sso_callback(request):
    return JsonResponse({"ok": True, "message": "SSO callback reached. Configure token exchange for the selected provider.", "code_received": bool(request.GET.get("code"))})
