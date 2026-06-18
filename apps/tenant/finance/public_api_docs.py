from rest_framework.response import Response
from rest_framework.views import APIView


class PublicIntegrationDocs(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            "authentication": "Use X-API-Key. Each key must be assigned the required scope.",
            "scopes": ["attendance-write", "messages-send", "payments-write", "transport-gps", "meetings-write", "integrations-admin"],
            "endpoints": [
                {"method": "GET", "path": "/api/v1/integrations/ready/", "scope": "integrations-admin"},
                {"method": "POST", "path": "/api/v1/integrations/biometric/attendance/", "scope": "attendance-write"},
                {"method": "POST", "path": "/api/v1/integrations/transport/gps/", "scope": "transport-gps"},
                {"method": "POST", "path": "/api/v1/integrations/meetings/create/", "scope": "meetings-write"},
                {"method": "GET", "path": "/api/v1/integrations/events/", "scope": "integrations-admin"},
                {"method": "POST", "path": "/api/v1/finance/provider-updates/mtn/", "scope": "provider callback"},
                {"method": "POST", "path": "/api/v1/finance/provider-updates/airtel/", "scope": "provider callback"},
            ],
            "setup_pages": ["/admin/integrations/", "/admin/integrations/providers/new/"],
        })
