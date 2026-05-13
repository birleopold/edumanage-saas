from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from .integration_api_views import (
    IntegrationHealth,
    IntegrationMessageLogs,
    IntegrationWebhookDeliveries,
    WhatsAppStatusCallback,
)


class WhoAmI(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"tenant": str(getattr(request, "tenant", ""))})


urlpatterns = [
    path("whoami/", WhoAmI.as_view(), name="api_whoami"),
    path("integrations/health/", IntegrationHealth.as_view(), name="api_integrations_health"),
    path("integrations/message-logs/", IntegrationMessageLogs.as_view(), name="api_integrations_message_logs"),
    path(
        "integrations/webhook-deliveries/",
        IntegrationWebhookDeliveries.as_view(),
        name="api_integrations_webhook_deliveries",
    ),
    path(
        "integrations/callbacks/whatsapp-status/",
        WhatsAppStatusCallback.as_view(),
        name="api_integrations_callback_whatsapp_status",
    ),
]
