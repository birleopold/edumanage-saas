import json
import uuid
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .invoicing import invoice_amounts
from .models import DuplicatePaymentAlert, MobilePaymentRequest, Payment, PaymentGatewayEvent


SUCCESS_STATUSES = {"SUCCESS", "SUCCESSFUL", "COMPLETED", "PAID", "APPROVED"}
FAILED_STATUSES = {"FAILED", "DECLINED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED"}


def _setting(name, default=""):
    return getattr(settings, name, default)


def _provider_config(network):
    if network == Payment.MTN_MOMO:
        return {
            "provider": PaymentGatewayEvent.MTN_MOMO,
            "url": _setting("MTN_MOMO_COLLECTION_URL"),
            "token": _setting("MTN_MOMO_COLLECTION_TOKEN"),
            "subscription_key": _setting("MTN_MOMO_SUBSCRIPTION_KEY"),
        }
    if network == Payment.AIRTEL_MONEY:
        return {
            "provider": PaymentGatewayEvent.AIRTEL_MONEY,
            "url": _setting("AIRTEL_MONEY_COLLECTION_URL"),
            "token": _setting("AIRTEL_MONEY_COLLECTION_TOKEN"),
            "subscription_key": _setting("AIRTEL_MONEY_SUBSCRIPTION_KEY"),
        }
    return {"provider": PaymentGatewayEvent.BANK, "url": "", "token": "", "subscription_key": ""}


def _send_provider_request(payment_request):
    config = _provider_config(payment_request.network)
    reference = payment_request.provider_reference or f"EDU-{payment_request.id}-{uuid.uuid4().hex[:8]}"
    payload = {
        "reference": reference,
        "amount": str(payment_request.amount),
        "phone_number": payment_request.phone_number,
        "invoice_id": payment_request.invoice_id,
        "student": str(payment_request.invoice.student),
    }
    if not config["url"]:
        return {"ok": True, "dry_run": True, "reference": reference, "payload": payload}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if config["token"]:
        headers["Authorization"] = f"Bearer {config['token']}"
    if config["subscription_key"]:
        headers["Ocp-Apim-Subscription-Key"] = config["subscription_key"]
    request = urllib.request.Request(config["url"], data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=_setting("MOBILE_MONEY_TIMEOUT_SECONDS", 20)) as response:
            text = response.read().decode("utf-8")
            try:
                data = json.loads(text or "{}")
            except json.JSONDecodeError:
                data = {"raw": text}
            return {"ok": 200 <= response.status < 300, "status_code": response.status, "reference": reference, "provider_response": data}
    except urllib.error.URLError as exc:
        return {"ok": False, "reference": reference, "error": str(exc)}


def detect_duplicate_payment(invoice, amount, reference=""):
    qs = Payment.objects.filter(invoice=invoice, amount=amount)
    if reference:
        exact = qs.filter(reference__iexact=reference).first()
        if exact:
            return exact
    return qs.filter(created_at__date=timezone.localdate()).first()


@transaction.atomic
def initiate_collection(*, invoice, amount, phone_number, network, requested_by=None):
    amounts = invoice_amounts(invoice)
    amount = Decimal(str(amount or amounts.balance))
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if amount > amounts.balance:
        raise ValueError("Amount cannot exceed invoice balance.")
    if detect_duplicate_payment(invoice, amount):
        raise ValueError("A similar payment already exists today. Please verify before paying again.")
    obj = MobilePaymentRequest.objects.create(invoice=invoice, amount=amount, phone_number=phone_number, network=network, requested_by=requested_by, status=MobilePaymentRequest.PROCESSING)
    result = _send_provider_request(obj)
    obj.provider_reference = result.get("reference", "")
    obj.provider_response = result
    obj.status = MobilePaymentRequest.PROCESSING if result.get("ok") else MobilePaymentRequest.FAILED
    obj.save(update_fields=["provider_reference", "provider_response", "status"])
    PaymentGatewayEvent.objects.create(provider=_provider_config(network)["provider"], event_type=PaymentGatewayEvent.INITIATED, payment_request=obj, provider_reference=obj.provider_reference, provider_status=obj.status, payload=result, processed=True, error_message=result.get("error", ""))
    return obj


def _callback_status(payload):
    status = str(payload.get("status") or payload.get("transaction_status") or payload.get("state") or "").upper()
    if status in SUCCESS_STATUSES:
        return MobilePaymentRequest.SUCCESSFUL
    if status in FAILED_STATUSES:
        return MobilePaymentRequest.FAILED
    return MobilePaymentRequest.PROCESSING


def _callback_reference(payload):
    return str(payload.get("reference") or payload.get("provider_reference") or payload.get("transaction_id") or payload.get("external_id") or "")


@transaction.atomic
def process_gateway_callback(provider, payload):
    reference = _callback_reference(payload)
    event = PaymentGatewayEvent.objects.create(provider=provider, event_type=PaymentGatewayEvent.CALLBACK, provider_reference=reference, provider_status=str(payload.get("status") or ""), payload=payload)
    payment_request = MobilePaymentRequest.objects.filter(provider_reference=reference).select_related("invoice").first()
    if not payment_request:
        event.error_message = "No matching payment request."
        event.save(update_fields=["error_message"])
        return event
    event.payment_request = payment_request
    status = _callback_status(payload)
    payment_request.status = status
    payment_request.provider_response = payload
    if status == MobilePaymentRequest.SUCCESSFUL and not payment_request.created_payment:
        duplicate = detect_duplicate_payment(payment_request.invoice, payment_request.amount, reference)
        if duplicate:
            DuplicatePaymentAlert.objects.create(payment=duplicate, duplicate_of=duplicate, reason=f"Gateway callback duplicate: {reference}")
            event.error_message = "Duplicate payment detected."
        else:
            payment = Payment.objects.create(invoice=payment_request.invoice, amount=payment_request.amount, method=Payment.MOBILE, mobile_network=payment_request.network, reference=reference, received_at=timezone.localdate())
            payment_request.created_payment = payment
            try:
                from .services import send_payment_receipt_for_payment
                send_payment_receipt_for_payment(payment)
            except Exception:
                pass
    payment_request.save(update_fields=["status", "provider_response", "created_payment"])
    event.processed = True
    event.save(update_fields=["payment_request", "processed", "error_message"])
    return event
