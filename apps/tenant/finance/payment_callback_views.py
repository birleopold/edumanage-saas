import json
import hashlib
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import PaymentGatewayEvent
from .payment_gateway import process_gateway_callback


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return request.POST.dict()


def _callback_secret(provider):
    setting_name = {
        PaymentGatewayEvent.MTN_MOMO: "MTN_MOMO_CALLBACK_SECRET",
        PaymentGatewayEvent.AIRTEL_MONEY: "AIRTEL_MONEY_CALLBACK_SECRET",
    }.get(provider)
    return getattr(settings, setting_name, "") if setting_name else ""


def _normalize_signature(value):
    value = (value or "").strip()
    if value.startswith("sha256="):
        return value.split("=", 1)[1]
    return value


def _signed_with_secret(request, secret):
    supplied_signature = request.headers.get("X-Webhook-Signature-256") or request.headers.get("X-Hub-Signature-256")
    if not supplied_signature:
        return False
    expected_signature = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, _normalize_signature(supplied_signature))


def _shared_secret_matches(request, secret):
    supplied_secret = request.headers.get("X-Callback-Secret") or request.headers.get("X-Webhook-Secret")
    return bool(supplied_secret and hmac.compare_digest(secret, supplied_secret))


def _callback_authorized(request, provider):
    secret = _callback_secret(provider)
    if not secret:
        return True
    return _shared_secret_matches(request, secret) or _signed_with_secret(request, secret)


def _handle_callback(request, provider):
    if not _callback_authorized(request, provider):
        return JsonResponse({"ok": False, "error": "invalid signature"}, status=401)
    event = process_gateway_callback(provider, _payload(request))
    return JsonResponse({"ok": event.processed, "event_id": event.id, "error": event.error_message})


@csrf_exempt
@require_POST
def mtn_momo_callback(request):
    return _handle_callback(request, PaymentGatewayEvent.MTN_MOMO)


@csrf_exempt
@require_POST
def airtel_money_callback(request):
    return _handle_callback(request, PaymentGatewayEvent.AIRTEL_MONEY)
