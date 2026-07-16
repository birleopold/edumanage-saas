import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenant.finance import services as finance_services
from apps.tenant.finance.models import IntegrationApiKey, OutboundMessageLog, WebhookDelivery, WebhookRetryQueueItem


class HasIntegrationApiKey(BasePermission):
    message = "Valid X-API-Key header is required."

    def has_permission(self, request, view):
        raw = (request.headers.get("X-API-Key") or "").strip()
        key_obj = IntegrationApiKey.resolve_active_key(raw)
        if not key_obj:
            return False
        key_obj.mark_used()
        request.integration_api_key = key_obj
        return True


class IntegrationHealth(APIView):
    authentication_classes = []
    permission_classes = [HasIntegrationApiKey]

    def get(self, request):
        return Response(
            {
                "ok": True,
                "time": timezone.now().isoformat(),
                "api_key": getattr(request.integration_api_key, "name", ""),
            }
        )


class IntegrationMessageLogs(APIView):
    authentication_classes = []
    permission_classes = [HasIntegrationApiKey]

    def get(self, request):
        limit_raw = request.GET.get("limit") or "50"
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        qs = OutboundMessageLog.objects.order_by("-created_at")
        status = (request.GET.get("status") or "").strip().upper()
        message_type = (request.GET.get("message_type") or "").strip().upper()
        channel = (request.GET.get("channel") or "").strip().upper()
        if status:
            qs = qs.filter(status=status)
        if message_type:
            qs = qs.filter(message_type=message_type)
        if channel:
            qs = qs.filter(channel=channel)

        rows = []
        for log in qs[:limit]:
            rows.append(
                {
                    "id": log.pk,
                    "message_type": log.message_type,
                    "channel": log.channel,
                    "status": log.status,
                    "phone_raw": log.phone_raw,
                    "phone_normalized": log.phone_normalized,
                    "invoice_id": log.invoice_id,
                    "payment_id": log.payment_id,
                    "provider_message_id": log.provider_message_id,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
            )
        return Response({"count": len(rows), "results": rows})


class IntegrationWebhookDeliveries(APIView):
    authentication_classes = []
    permission_classes = [HasIntegrationApiKey]

    def get(self, request):
        limit_raw = request.GET.get("limit") or "50"
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        qs = WebhookDelivery.objects.select_related("endpoint").order_by("-created_at")
        success = (request.GET.get("success") or "").strip().lower()
        if success in ("true", "1", "yes"):
            qs = qs.filter(success=True)
        elif success in ("false", "0", "no"):
            qs = qs.filter(success=False)

        rows = []
        for d in qs[:limit]:
            rows.append(
                {
                    "id": d.pk,
                    "endpoint": d.endpoint.name if d.endpoint_id else "",
                    "event_type": d.event_type,
                    "status_code": d.status_code,
                    "success": d.success,
                    "error_message": d.error_message,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
            )
        retry_qs = WebhookRetryQueueItem.objects.all()
        return Response(
            {
                "count": len(rows),
                "active_retry_count": retry_qs.filter(is_active=True).count(),
                "terminal_retry_count": retry_qs.filter(is_active=False, attempt_count__gte=1).count(),
                "failed_delivery_count": WebhookDelivery.objects.filter(success=False).count(),
                "results": rows,
            }
        )


class WhatsAppStatusCallback(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        secret = (getattr(settings, "WHATSAPP_STATUS_WEBHOOK_SECRET", "") or "").strip()
        provided_sig = (request.headers.get("X-Webhook-Signature-256") or "").strip().lower()
        raw = request.body or b"{}"
        signature_valid = True
        if secret:
            expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
            signature_valid = bool(provided_sig and hmac.compare_digest(provided_sig, expected))
        if not signature_valid:
            payload = {}
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {}
            finance_services.process_inbound_whatsapp_status_callback(payload, signature_valid=False)
            return Response({"ok": False, "error": "invalid signature"}, status=401)

        payload = {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return Response({"ok": False, "error": "invalid json"}, status=400)

        summary = finance_services.process_inbound_whatsapp_status_callback(payload, signature_valid=True)
        return Response({"ok": True, **summary})
