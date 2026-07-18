import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import PaymentGatewayEvent
from .payment_gateway import process_gateway_callback

logger = logging.getLogger("edumanage.security")

def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return request.POST.dict()

def _callback_secret(provider):
    setting_name = {PaymentGatewayEvent.MTN_MOMO: "MTN_MOMO_CALLBACK_SECRET", PaymentGatewayEvent.AIRTEL_MONEY: "AIRTEL_MONEY_CALLBACK_SECRET"}.get(provider)
    return (getattr(settings, setting_name, "") or "").strip() if setting_name else ""

def _normalize_signature(value):
    value = (value or "").strip()
    return value.split("=", 1)[1] if value.startswith("sha256=") else value

def _signed_with_secret(request, secret):
    supplied = request.headers.get("X-Webhook-Signature-256") or request.headers.get("X-Hub-Signature-256")
    if not supplied:
        return False
    expected = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, _normalize_signature(supplied))

def _shared_secret_matches(request, secret):
    supplied = request.headers.get("X-Callback-Secret") or request.headers.get("X-Webhook-Secret")
    return bool(supplied and hmac.compare_digest(secret, supplied))

def _callback_authorized(request, provider):
    secret = _callback_secret(provider)
    return bool(secret and (_shared_secret_matches(request, secret) or _signed_with_secret(request, secret)))

def _handle_callback(request, provider):
    if not getattr(settings, "PAYMENT_CALLBACKS_ENABLED", False):
        logger.warning("Rejected disabled payment callback provider=%s", provider)
        return JsonResponse({"ok": False, "error": "payment callbacks are disabled"}, status=503)
    if not _callback_secret(provider):
        logger.error("Rejected payment callback because provider secret is not configured provider=%s", provider)
        return JsonResponse({"ok": False, "error": "payment callback is not configured"}, status=503)
    if not _callback_authorized(request, provider):
        logger.warning("Rejected payment callback with invalid signature provider=%s", provider)
        return JsonResponse({"ok": False, "error": "invalid signature"}, status=401)
    event = process_gateway_callback(provider, _payload(request))
    return JsonResponse({"ok": event.processed, "event_id": event.id, "error": event.error_message}, status=200 if event.processed else 400)

@csrf_exempt
@require_POST
def mtn_momo_callback(request):
    return _handle_callback(request, PaymentGatewayEvent.MTN_MOMO)

@csrf_exempt
@require_POST
def airtel_money_callback(request):
    return _handle_callback(request, PaymentGatewayEvent.AIRTEL_MONEY)
