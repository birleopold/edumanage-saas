from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenant.academics.models import CourseOffering

from .integration_security import HasScopedIntegrationKey
from .integration_services import create_meeting_link, process_biometric_event, provider_readiness_summary, record_vehicle_gps
from .models import IntegrationEventLog, MeetingSessionLink


class Ready(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "integrations-admin"

    def get(self, request):
        return Response(provider_readiness_summary())


class BioIn(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "attendance-write"

    def post(self, request):
        item = process_biometric_event(request.data, api_key=request.integration_api_key)
        return Response({"id": item.id, "processed": item.processed, "error": item.error_message})


class GpsIn(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "transport-gps"

    def post(self, request):
        item = record_vehicle_gps(request.data, api_key=request.integration_api_key)
        return Response({"id": item.id, "vehicle_id": item.vehicle_id})


class MeetNew(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "meetings-write"

    def post(self, request):
        offering = CourseOffering.objects.filter(pk=request.data.get("offering_id")).first() if request.data.get("offering_id") else None
        link = create_meeting_link(provider_type=request.data.get("provider_type") or MeetingSessionLink.ZOOM, title=request.data.get("title") or "Online lesson", offering=offering)
        return Response({"id": link.id, "meeting_url": link.meeting_url})


class Events(APIView):
    authentication_classes = []
    permission_classes = [HasScopedIntegrationKey]
    required_scope = "integrations-admin"

    def get(self, request):
        rows = IntegrationEventLog.objects.order_by("-created_at")[:100]
        return Response({"results": [{"id": r.id, "event_type": r.event_type, "status": r.status, "error": r.error_message} for r in rows]})
