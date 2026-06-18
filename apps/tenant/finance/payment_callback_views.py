import json

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


@csrf_exempt
@require_POST
def mtn_momo_callback(request):
    event = process_gateway_callback(PaymentGatewayEvent.MTN_MOMO, _payload(request))
    return JsonResponse({"ok": event.processed, "event_id": event.id, "error": event.error_message})


@csrf_exempt
@require_POST
def airtel_money_callback(request):
    event = process_gateway_callback(PaymentGatewayEvent.AIRTEL_MONEY, _payload(request))
    return JsonResponse({"ok": event.processed, "event_id": event.id, "error": event.error_message})
