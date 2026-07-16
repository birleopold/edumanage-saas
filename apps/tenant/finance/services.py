"""
Finance helpers: invoice calculations, fee carry-forward, SMS/WhatsApp dispatch,
message logging, and retry support.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from inspect import signature
from typing import Callable, List, Optional, Tuple
from urllib import error, request

from django.conf import settings
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger("edumanage.finance")


def format_money_for_message(amount: Decimal | float | str | None, currency_code: str = "UGX") -> str:
    if amount is None:
        return "—"
    code = (currency_code or "UGX").strip().upper() or "UGX"
    try:
        val = Decimal(str(amount))
    except Exception:
        return str(amount)
    if code == "UGX":
        return f"{code} {val:,.0f}"
    return f"{code} {val:,.2f}"


def _fee_reminder_handler() -> Optional[Callable[[str, str], bool]]:
    raw = getattr(settings, "FEE_REMINDER_HANDLER", None)
    if raw is None:
        raw = getattr(settings, "FEE_REMINDER_SMS_HANDLER", None)
    if raw is None:
        return None
    if callable(raw):
        return raw
    if isinstance(raw, str):
        mod_path, _, attr = raw.rpartition(".")
        if not mod_path or not attr:
            return None
        mod = import_module(mod_path)
        fn = getattr(mod, attr, None)
        return fn if callable(fn) else None
    return None


def _current_channel() -> str:
    return (getattr(settings, "FEE_REMINDER_CHANNEL", "SMS") or "SMS").strip().upper()


def _parent_allows_channel(parent, channel: str) -> bool:
    channel = (channel or "").upper()
    if channel == "WHATSAPP":
        return bool(getattr(parent, "allow_whatsapp_alerts", True))
    return bool(getattr(parent, "allow_sms_alerts", True))


def normalize_phone_for_whatsapp(phone: str, default_country_code: str = "256") -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"[^\d+]", "", raw)
    if not cleaned:
        return ""
    if cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned)
    elif cleaned.startswith("00"):
        digits = re.sub(r"\D", "", cleaned[2:])
    else:
        digits = re.sub(r"\D", "", cleaned)
        cc = re.sub(r"\D", "", default_country_code or "") or "256"
        if digits.startswith("0"):
            digits = cc + digits[1:]
        elif not digits.startswith(cc):
            digits = cc + digits
    if len(digits) < 9 or len(digits) > 15:
        return ""
    return digits


def build_parent_invoice_url(invoice) -> str:
    base = (getattr(settings, "FEE_REMINDER_PORTAL_BASE_URL", "") or "").strip().rstrip("/")
    return f"{base}/parent/finance/invoices/{invoice.pk}/" if base else ""


def build_parent_payment_receipt_url(payment) -> str:
    base = (getattr(settings, "FEE_REMINDER_PORTAL_BASE_URL", "") or "").strip().rstrip("/")
    return f"{base}/parent/finance/invoices/{payment.invoice.pk}/payments/{payment.pk}/receipt/" if base else ""


def _extract_provider_message_id(provider_response) -> str:
    if not isinstance(provider_response, dict):
        return ""
    messages = provider_response.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0] or {}
        if isinstance(first, dict):
            return str(first.get("id") or "")
    return str(provider_response.get("id") or "")


def dispatch_fee_message(phone: str, message: str, *, channel_override: str | None = None) -> dict:
    phone = (phone or "").strip()
    if not phone:
        return {"ok": False, "phone_normalized": "", "channel": channel_override or _current_channel(), "error": "empty phone"}

    channel = (channel_override or _current_channel() or "SMS").strip().upper()
    normalized_phone = phone
    if channel == "WHATSAPP":
        normalized_phone = normalize_phone_for_whatsapp(phone, getattr(settings, "FEE_REMINDER_DEFAULT_COUNTRY_CODE", "256"))
        if not normalized_phone:
            return {"ok": False, "phone_normalized": "", "channel": channel, "error": "invalid whatsapp phone"}

    handler = _fee_reminder_handler()
    if handler:
        try:
            params = signature(handler).parameters
            response = handler(normalized_phone, message, channel=channel) if "channel" in params else handler(normalized_phone, message)
            ok = bool(response)
            provider_response = response if isinstance(response, dict) else {}
            return {
                "ok": ok,
                "phone_normalized": normalized_phone,
                "channel": channel,
                "provider_response": provider_response,
                "provider_message_id": _extract_provider_message_id(provider_response),
                "error": "" if ok else "handler returned falsey value",
            }
        except Exception as exc:
            logger.exception("Outbound message handler failed")
            return {"ok": False, "phone_normalized": normalized_phone, "channel": channel, "provider_response": {}, "provider_message_id": "", "error": f"handler exception:{exc.__class__.__name__}"}

    # No provider configured: behave as a safe local success so demos and tests do not break.
    logger.info("Outbound %s no-handler dry success to=%s msg=%s", channel, normalized_phone, message[:160])
    return {"ok": True, "phone_normalized": normalized_phone, "channel": channel, "provider_response": {}, "provider_message_id": "", "error": ""}


def dispatch_fee_reminder_sms(phone: str, message: str) -> bool:
    return bool(dispatch_fee_message(phone, message).get("ok"))


def parent_phones_for_student(student) -> List[str]:
    from apps.tenant.parents.models import ParentStudentLink

    channel = _current_channel()
    phones: List[str] = []
    seen = set()
    links = ParentStudentLink.objects.filter(student=student).select_related("parent").order_by("-is_primary", "parent__last_name")
    for link in links:
        if not _parent_allows_channel(link.parent, channel):
            continue
        phone = (link.parent.phone or "").strip()
        if phone and phone not in seen:
            phones.append(phone)
            seen.add(phone)
    return phones


def _create_outbound_log(*, message_type: str, channel: str, invoice=None, payment=None, phone_raw: str = "", phone_normalized: str = "", status: str = "FAILED", message: str = "", provider_message_id: str = "", provider_response: Optional[dict] = None, error_message: str = ""):
    from .models import OutboundMessageLog

    obj = OutboundMessageLog.objects.create(
        message_type=message_type,
        channel=channel,
        invoice=invoice,
        payment=payment,
        phone_raw=phone_raw or "",
        phone_normalized=phone_normalized or "",
        status=status,
        message=message or "",
        provider_message_id=provider_message_id or "",
        provider_response=provider_response or {},
        error_message=error_message or "",
    )
    _dispatch_webhook_event_for_message_log(obj)
    return obj


def build_fee_reminder_message(invoice, *, currency_code: str = "UGX", school_name: str = "", parent=None) -> str:
    try:
        from . import outbound_copy
        from .models import OutboundMessageLog
        body = outbound_copy.get_active_template_body(OutboundMessageLog.FEE_REMINDER)
        if body:
            ctx = outbound_copy.fee_reminder_context(invoice, currency_code=currency_code, school_name=school_name, parent=parent)
            return outbound_copy.apply_communication_placeholders(body, ctx).strip()[:480]
    except Exception:
        logger.exception("Fee reminder template failed; falling back to default copy")
    student = invoice.student
    amount = format_money_for_message(invoice.balance(), currency_code)
    bits = []
    if school_name:
        bits.append(school_name[:60])
    bits.append(f"Fees: {student.first_name} {student.last_name} ({invoice.reference or invoice.pk}). Balance due: {amount}.")
    if invoice.due_date:
        bits.append(f"Due: {invoice.due_date.isoformat()}.")
    url = build_parent_invoice_url(invoice)
    if url:
        bits.append(f"Details: {url}")
    bits.append("Please pay through approved school channels.")
    return " ".join(bits)[:480]


def build_payment_receipt_message(payment, *, currency_code: str = "UGX", school_name: str = "", parent=None) -> str:
    try:
        from . import outbound_copy
        from .models import OutboundMessageLog
        body = outbound_copy.get_active_template_body(OutboundMessageLog.PAYMENT_RECEIPT)
        if body:
            ctx = outbound_copy.payment_receipt_context(payment, currency_code=currency_code, school_name=school_name, parent=parent)
            return outbound_copy.apply_communication_placeholders(body, ctx).strip()[:480]
    except Exception:
        logger.exception("Payment receipt template failed; falling back to default copy")
    student = payment.invoice.student
    amount = format_money_for_message(payment.amount, currency_code)
    bits = []
    if school_name:
        bits.append(school_name[:60])
    bits.append(f"Payment received for {student.first_name} {student.last_name}. Amount: {amount}. Ref: {payment.reference or payment.pk}.")
    url = build_parent_payment_receipt_url(payment)
    if url:
        bits.append(f"Receipt: {url}")
    bits.append("Thank you.")
    return " ".join(bits)[:480]


def build_absence_alert_message(entry, *, school_name: str = "", parent=None) -> str:
    try:
        from . import outbound_copy
        from .models import OutboundMessageLog
        body = outbound_copy.get_active_template_body(OutboundMessageLog.ABSENCE_ALERT)
        if body:
            ctx = outbound_copy.absence_alert_context(entry, school_name=school_name, parent=parent)
            return outbound_copy.apply_communication_placeholders(body, ctx).strip()[:480]
    except Exception:
        logger.exception("Absence alert template failed; falling back to default copy")
    student = entry.student
    session = entry.session
    status = (entry.status or "").replace("_", " ").title()
    course = getattr(getattr(session, "offering", None), "course", None)
    bits = []
    if school_name:
        bits.append(school_name[:60])
    bits.append(f"Attendance alert: {student.first_name} {student.last_name} marked {status} on {session.date.isoformat()}.")
    if course:
        bits.append(f"Class: {course}.")
    if entry.note:
        bits.append(f"Note: {entry.note[:120]}")
    return " ".join(bits)[:480]


def build_urgent_announcement_message(announcement, *, school_name: str = "", parent=None) -> str:
    try:
        from . import outbound_copy
        from .models import OutboundMessageLog
        body = outbound_copy.get_active_template_body(OutboundMessageLog.URGENT_ANNOUNCEMENT)
        if body:
            ctx = outbound_copy.urgent_announcement_context(announcement, school_name=school_name, parent=parent)
            return outbound_copy.apply_communication_placeholders(body, ctx).strip()[:480]
    except Exception:
        logger.exception("Urgent announcement template failed; falling back to default copy")
    bits = []
    if school_name:
        bits.append(school_name[:60])
    bits.append(f"URGENT: {announcement.title}")
    bits.append((announcement.body or "").strip()[:320])
    return " ".join([b for b in bits if b])[:480]


def _dispatch_to_phone(*, message_type: str, channel: str, phone: str, message: str, invoice=None, payment=None, provider_response_extra: dict | None = None, dry_run: bool = False) -> dict:
    from .models import OutboundMessageLog

    if dry_run:
        _create_outbound_log(message_type=message_type, channel=channel, invoice=invoice, payment=payment, phone_raw=phone, status=OutboundMessageLog.DRY_RUN, message=message, provider_response=provider_response_extra or {})
        return {"phone": phone, "status": "dry_run", "channel": channel, "message": message}
    dispatch = dispatch_fee_message(phone, message, channel_override=channel)
    ok = bool(dispatch.get("ok"))
    provider_response = dict(provider_response_extra or {})
    provider_response["provider"] = dispatch.get("provider_response", {})
    _create_outbound_log(
        message_type=message_type,
        channel=dispatch.get("channel", channel),
        invoice=invoice,
        payment=payment,
        phone_raw=phone,
        phone_normalized=dispatch.get("phone_normalized", ""),
        status=OutboundMessageLog.SENT if ok else OutboundMessageLog.FAILED,
        message=message,
        provider_message_id=dispatch.get("provider_message_id", ""),
        provider_response=provider_response,
        error_message=dispatch.get("error", ""),
    )
    return {"phone": phone, "phone_normalized": dispatch.get("phone_normalized", ""), "status": "sent" if ok else "failed", "channel": dispatch.get("channel", channel), "message": message}


def send_test_message(*, phone: str, message: str, channel: str | None = None, dry_run: bool = False) -> dict:
    from .models import OutboundMessageLog

    selected_channel = (channel or _current_channel() or "SMS").strip().upper()
    msg = (message or "").strip()[:480] or "EduManage test message. Please ignore."
    result = _dispatch_to_phone(
        message_type=OutboundMessageLog.URGENT_ANNOUNCEMENT,
        channel=selected_channel,
        phone=phone,
        message=msg,
        provider_response_extra={"manual_test": True},
        dry_run=dry_run,
    )
    return result


def send_fee_reminder_for_invoice(invoice, *, currency_code: str = "UGX", school_name: str = "", dry_run: bool = False) -> List[dict]:
    from . import outbound_copy
    from .models import OutboundMessageLog

    channel = _current_channel()
    phones = parent_phones_for_student(invoice.student)
    if not phones:
        _create_outbound_log(message_type=OutboundMessageLog.FEE_REMINDER, channel=channel, invoice=invoice, status=OutboundMessageLog.NO_PHONE, error_message="No eligible parent phone")
        return [{"phone": "", "status": "no_phone", "channel": channel}]
    results = []
    for phone in phones:
        parent = outbound_copy.resolve_parent_for_student_phone(invoice.student, phone)
        msg = build_fee_reminder_message(invoice, currency_code=currency_code, school_name=school_name, parent=parent)
        results.append(_dispatch_to_phone(message_type=OutboundMessageLog.FEE_REMINDER, channel=channel, phone=phone, message=msg, invoice=invoice, dry_run=dry_run))
    return results


def send_payment_receipt_for_payment(payment, *, currency_code: str = "UGX", school_name: str = "", dry_run: bool = False) -> List[dict]:
    from . import outbound_copy
    from .models import OutboundMessageLog

    invoice = payment.invoice
    channel = _current_channel()
    phones = parent_phones_for_student(invoice.student)
    if not phones:
        _create_outbound_log(message_type=OutboundMessageLog.PAYMENT_RECEIPT, channel=channel, invoice=invoice, payment=payment, status=OutboundMessageLog.NO_PHONE, error_message="No eligible parent phone")
        return [{"phone": "", "status": "no_phone", "channel": channel}]
    results = []
    for phone in phones:
        parent = outbound_copy.resolve_parent_for_student_phone(invoice.student, phone)
        msg = build_payment_receipt_message(payment, currency_code=currency_code, school_name=school_name, parent=parent)
        results.append(_dispatch_to_phone(message_type=OutboundMessageLog.PAYMENT_RECEIPT, channel=channel, phone=phone, message=msg, invoice=invoice, payment=payment, dry_run=dry_run))
    return results


def send_absence_alerts_for_session(session, *, include_late: bool = False, school_name: str = "", dry_run: bool = False) -> dict:
    from apps.tenant.attendance.models import AttendanceEntry

    statuses = [AttendanceEntry.ABSENT]
    if include_late:
        statuses.append(AttendanceEntry.LATE)
    entries = list(AttendanceEntry.objects.filter(session=session, status__in=statuses).select_related("student", "session", "session__offering", "session__offering__course"))
    return _send_absence_alerts_for_entries(entries, school_name=school_name, dry_run=dry_run)


def send_absence_alerts_for_date(target_date: date | str, *, campus_id: int | None = None, include_late: bool = False, school_name: str = "", dry_run: bool = False) -> dict:
    from apps.tenant.attendance.models import AttendanceEntry

    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    statuses = [AttendanceEntry.ABSENT]
    if include_late:
        statuses.append(AttendanceEntry.LATE)
    qs = AttendanceEntry.objects.filter(session__date=target_date, status__in=statuses).select_related("student", "student__campus", "session", "session__offering", "session__offering__course")
    if campus_id:
        qs = qs.filter(student__campus_id=campus_id)
    return _send_absence_alerts_for_entries(list(qs), school_name=school_name, dry_run=dry_run)


def _send_absence_alerts_for_entries(entries, *, school_name: str = "", dry_run: bool = False) -> dict:
    from . import outbound_copy
    from .models import OutboundMessageLog

    channel = _current_channel()
    sent = failed = no_phone = dry = 0
    details = []
    for entry in entries:
        phones = parent_phones_for_student(entry.student)
        msg_base = build_absence_alert_message(entry, school_name=school_name, parent=None)
        if not phones:
            no_phone += 1
            _create_outbound_log(message_type=OutboundMessageLog.ABSENCE_ALERT, channel=channel, phone_raw="", status=OutboundMessageLog.NO_PHONE, message=msg_base, error_message=f"No eligible parent phone for student_id={entry.student_id}", provider_response={"entry_id": entry.pk})
            details.append({"entry_id": entry.pk, "status": "no_phone"})
            continue
        for phone in phones:
            parent = outbound_copy.resolve_parent_for_student_phone(entry.student, phone)
            msg = build_absence_alert_message(entry, school_name=school_name, parent=parent)
            res = _dispatch_to_phone(message_type=OutboundMessageLog.ABSENCE_ALERT, channel=channel, phone=phone, message=msg, provider_response_extra={"entry_id": entry.pk}, dry_run=dry_run)
            if res["status"] == "sent":
                sent += 1
            elif res["status"] == "failed":
                failed += 1
            elif res["status"] == "dry_run":
                dry += 1
            details.append({"entry_id": entry.pk, **res})
    return {"entries": len(entries), "sent": sent, "failed": failed, "no_phone": no_phone, "dry_run_count": dry, "details": details}


def send_urgent_announcement_broadcast(announcement, *, campus_id: int | None = None, school_name: str = "", dry_run: bool = False) -> dict:
    from apps.tenant.announcements.models import Announcement
    from apps.tenant.parents.models import ParentProfile
    from .models import OutboundMessageLog

    if announcement.audience not in (Announcement.ALL, Announcement.PARENTS):
        return {"sent": 0, "failed": 0, "no_phone": 0, "dry_run_count": 0, "details": [], "skipped": True}
    channel = _current_channel()
    parents = ParentProfile.objects.filter(is_active=True).order_by("last_name", "first_name")
    if campus_id:
        parents = parents.filter(parentstudentlink__student__campus_id=campus_id).distinct()
    sent = failed = no_phone = dry = 0
    details = []
    for parent in parents:
        if not _parent_allows_channel(parent, channel):
            continue
        phone = (parent.phone or "").strip()
        msg = build_urgent_announcement_message(announcement, school_name=school_name, parent=parent)
        if not phone:
            no_phone += 1
            _create_outbound_log(message_type=OutboundMessageLog.URGENT_ANNOUNCEMENT, channel=channel, phone_raw="", status=OutboundMessageLog.NO_PHONE, message=msg, error_message=f"No phone for parent_id={parent.pk}", provider_response={"announcement_id": announcement.pk})
            details.append({"parent_id": parent.pk, "status": "no_phone"})
            continue
        res = _dispatch_to_phone(message_type=OutboundMessageLog.URGENT_ANNOUNCEMENT, channel=channel, phone=phone, message=msg, provider_response_extra={"announcement_id": announcement.pk, "parent_id": parent.pk}, dry_run=dry_run)
        if res["status"] == "sent":
            sent += 1
        elif res["status"] == "failed":
            failed += 1
        elif res["status"] == "dry_run":
            dry += 1
        details.append({"parent_id": parent.pk, **res})
    return {"parents_considered": parents.count(), "sent": sent, "failed": failed, "no_phone": no_phone, "dry_run_count": dry, "details": details}


def retry_outbound_message_log(log, *, dry_run: bool = False) -> dict:
    from .models import OutboundMessageLog

    phone = (log.phone_raw or log.phone_normalized or "").strip()
    msg = (log.message or "").strip()
    if not phone or not msg:
        _create_outbound_log(message_type=log.message_type, channel=log.channel, invoice=log.invoice, payment=log.payment, phone_raw=phone, status=OutboundMessageLog.FAILED, message=msg, error_message="retry skipped: missing phone or message", provider_response={"retry_of_log_id": log.pk})
        return {"status": "skipped", "reason": "missing phone or message"}
    if dry_run:
        _create_outbound_log(message_type=log.message_type, channel=log.channel, invoice=log.invoice, payment=log.payment, phone_raw=phone, status=OutboundMessageLog.DRY_RUN, message=msg, provider_response={"retry_of_log_id": log.pk})
        return {"status": "dry_run"}
    dispatch = dispatch_fee_message(phone, msg, channel_override=log.channel)
    ok = bool(dispatch.get("ok"))
    _create_outbound_log(message_type=log.message_type, channel=dispatch.get("channel", log.channel), invoice=log.invoice, payment=log.payment, phone_raw=phone, phone_normalized=dispatch.get("phone_normalized", ""), status=OutboundMessageLog.SENT if ok else OutboundMessageLog.FAILED, message=msg, provider_message_id=dispatch.get("provider_message_id", ""), provider_response={"retry_of_log_id": log.pk, "provider": dispatch.get("provider_response", {})}, error_message=dispatch.get("error", ""))
    return {"status": "sent" if ok else "failed"}


def retry_outbound_message_logs(*, limit: int = 100, dry_run: bool = False, only_failed: bool = True, message_type: str = "", log_queryset=None) -> dict:
    from .models import OutboundMessageLog

    max_limit = max(1, min(int(limit or 100), 1000))
    qs = log_queryset if log_queryset is not None else OutboundMessageLog.objects.select_related("invoice", "payment")
    qs = qs.order_by("-created_at")
    if only_failed:
        qs = qs.filter(status=OutboundMessageLog.FAILED)
    if message_type:
        qs = qs.filter(message_type=message_type.strip().upper())
    processed = sent = failed = skipped = dry = 0
    logs = []
    for log in qs[:max_limit]:
        processed += 1
        result = retry_outbound_message_log(log, dry_run=dry_run)
        status = result.get("status")
        if status == "sent":
            sent += 1
        elif status == "failed":
            failed += 1
        elif status == "skipped":
            skipped += 1
        elif status == "dry_run":
            dry += 1
        logs.append({"log_id": log.pk, **result})
    return {"processed": processed, "sent": sent, "failed": failed, "skipped": skipped, "dry_run_count": dry, "dry_run": dry_run, "logs": logs}


def retry_outbound_message_log_by_id(log_id: int, *, dry_run: bool = False) -> dict:
    from .models import OutboundMessageLog
    log = OutboundMessageLog.objects.select_related("invoice", "payment").get(pk=log_id)
    return retry_outbound_message_log(log, dry_run=dry_run)


def messaging_readiness_snapshot(*, sample_limit: int = 50, invoice_queryset=None, log_queryset=None) -> dict:
    from .models import Invoice, OutboundMessageLog

    handler = _fee_reminder_handler()
    channel = _current_channel()
    token = (getattr(settings, "WHATSAPP_CLOUD_ACCESS_TOKEN", "") or "").strip()
    phone_id = (getattr(settings, "WHATSAPP_CLOUD_PHONE_NUMBER_ID", "") or "").strip()
    portal_base = (getattr(settings, "FEE_REMINDER_PORTAL_BASE_URL", "") or "").strip()
    invoice_qs = invoice_queryset if invoice_queryset is not None else Invoice.objects.select_related("student").prefetch_related("lines", "payments")
    log_qs = log_queryset if log_queryset is not None else OutboundMessageLog.objects.all()
    invoices = list(invoice_qs[: max(sample_limit, 1)])
    outstanding = [invoice for invoice in invoices if invoice.balance() > 0]
    return {
        "channel": channel,
        "handler_configured": bool(getattr(settings, "FEE_REMINDER_HANDLER", None) or getattr(settings, "FEE_REMINDER_SMS_HANDLER", None)),
        "handler_resolved": bool(handler),
        "portal_base_configured": bool(portal_base),
        "whatsapp_token_set": bool(token),
        "whatsapp_phone_number_id_set": bool(phone_id),
        "invoice_sample_size": len(invoices),
        "outstanding_invoices_in_sample": len(outstanding),
        "outstanding_with_parent_phone_in_sample": sum(1 for invoice in outstanding if parent_phones_for_student(invoice.student)),
        "failed_logs_count": log_qs.filter(status=OutboundMessageLog.FAILED).count(),
    }


def _webhook_signature(secret: str, payload_bytes: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest() if secret else ""


def _deliver_webhook(endpoint, event_type: str, payload: dict) -> dict:
    payload_bytes = json.dumps(payload).encode("utf-8")
    timeout = int(getattr(settings, "WEBHOOK_REQUEST_TIMEOUT_SECONDS", 8) or 8)
    sig = _webhook_signature(endpoint.secret or "", payload_bytes)
    req = request.Request(endpoint.target_url, data=payload_bytes, headers={"Content-Type": "application/json", "X-Webhook-Event": event_type, "X-Webhook-Signature-256": sig}, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status_code = int(getattr(resp, "status", None) or resp.getcode())
            body = resp.read()
            return {"status_code": status_code, "success": 200 <= status_code < 300, "response_body": body.decode("utf-8", errors="replace")[:1000] if body else "", "error_message": ""}
    except error.HTTPError as exc:
        return {"status_code": int(getattr(exc, "code", 0) or 0) or None, "success": False, "response_body": "", "error_message": f"http_error:{getattr(exc, 'code', 'unknown')}"}
    except error.URLError as exc:
        return {"status_code": None, "success": False, "response_body": "", "error_message": f"url_error:{getattr(exc, 'reason', 'unknown')}"}
    except Exception as exc:
        return {"status_code": None, "success": False, "response_body": "", "error_message": f"exception:{exc.__class__.__name__}"}


def _enqueue_webhook_retry_item(endpoint, event_type: str, payload: dict, error_message: str, status_code=None) -> None:
    from .models import WebhookRetryQueueItem
    WebhookRetryQueueItem.objects.create(endpoint=endpoint, event_type=event_type, payload=payload, attempt_count=0, max_attempts=int(getattr(settings, "WEBHOOK_MAX_RETRY_ATTEMPTS", 5) or 5), next_attempt_at=timezone.now() + timedelta(seconds=int(getattr(settings, "WEBHOOK_RETRY_BASE_SECONDS", 30) or 30)), is_active=True, last_error_message=error_message or "", last_status_code=status_code)


def _dispatch_webhook_event_for_message_log(log_obj) -> None:
    try:
        from .models import WebhookDelivery, WebhookEndpoint
        event_type = "message_log.created"
        endpoints = WebhookEndpoint.objects.filter(is_active=True, event_type=event_type)
        payload = {"event": event_type, "tenant": str(getattr(getattr(log_obj, "_state", None), "db", "default")), "message_log": {"id": log_obj.pk, "message_type": log_obj.message_type, "channel": log_obj.channel, "status": log_obj.status, "phone_raw": log_obj.phone_raw, "phone_normalized": log_obj.phone_normalized, "provider_message_id": log_obj.provider_message_id, "created_at": log_obj.created_at.isoformat() if log_obj.created_at else None, "invoice_id": log_obj.invoice_id, "payment_id": log_obj.payment_id}}
        for endpoint in endpoints:
            result = _deliver_webhook(endpoint, event_type, payload)
            WebhookDelivery.objects.create(endpoint=endpoint, event_type=event_type, payload=payload, status_code=result["status_code"], success=result["success"], response_body=result["response_body"], error_message=result["error_message"])
            if not result["success"]:
                _enqueue_webhook_retry_item(endpoint, event_type, payload, result["error_message"], result["status_code"])
    except Exception:
        logger.exception("Webhook dispatch failed for message log")


def process_webhook_retry_queue(*, limit: int = 100, dry_run: bool = False) -> dict:
    from .models import WebhookDelivery, WebhookRetryQueueItem

    items = list(WebhookRetryQueueItem.objects.select_related("endpoint").filter(is_active=True, next_attempt_at__lte=timezone.now()).order_by("next_attempt_at", "id")[: max(1, min(int(limit or 100), 1000))])
    processed = sent = failed = deactivated = 0
    details = []
    base_delay = int(getattr(settings, "WEBHOOK_RETRY_BASE_SECONDS", 30) or 30)
    for item in items:
        processed += 1
        if dry_run:
            details.append({"item_id": item.pk, "status": "dry_run"})
            continue
        result = _deliver_webhook(item.endpoint, item.event_type, item.payload)
        WebhookDelivery.objects.create(endpoint=item.endpoint, event_type=item.event_type, payload=item.payload, status_code=result["status_code"], success=result["success"], response_body=result["response_body"], error_message=result["error_message"])
        item.attempt_count += 1
        item.last_error_message = result["error_message"] or ""
        item.last_status_code = result["status_code"]
        if result["success"]:
            item.is_active = False
            sent += 1
            deactivated += 1
            details.append({"item_id": item.pk, "status": "sent"})
        else:
            failed += 1
            if item.attempt_count >= item.max_attempts:
                item.is_active = False
                deactivated += 1
                details.append({"item_id": item.pk, "status": "failed_terminal"})
            else:
                delay = base_delay * (2 ** max(item.attempt_count - 1, 0))
                item.next_attempt_at = timezone.now() + timedelta(seconds=delay)
                details.append({"item_id": item.pk, "status": "failed_retry_scheduled", "next_delay_s": delay})
        item.save(update_fields=["attempt_count", "last_error_message", "last_status_code", "next_attempt_at", "is_active", "updated_at"])
    return {"processed": processed, "sent": sent, "failed": failed, "deactivated": deactivated, "dry_run": dry_run, "details": details}


def process_inbound_whatsapp_status_callback(payload: dict, *, signature_valid: bool) -> dict:
    from .models import InboundWebhookEvent, OutboundMessageLog

    updates = 0
    last_status = ""
    error_message = ""
    try:
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for st in value.get("statuses") or []:
                    msg_id = (st.get("id") or "").strip()
                    if not msg_id:
                        continue
                    status = (st.get("status") or "").strip().lower()
                    for log in OutboundMessageLog.objects.filter(provider_message_id=msg_id):
                        provider_resp = dict(log.provider_response or {})
                        provider_resp["delivery_callback"] = st
                        log.provider_response = provider_resp
                        log.provider_delivery_status = status[:32]
                        log.provider_delivery_updated_at = timezone.now()
                        if status == "failed":
                            log.status = OutboundMessageLog.FAILED
                            if st.get("errors"):
                                log.error_message = str(st.get("errors"))[:1000]
                        elif status in ("delivered", "read"):
                            log.status = OutboundMessageLog.SENT
                        log.save(update_fields=["provider_response", "provider_delivery_status", "provider_delivery_updated_at", "status", "error_message"])
                        updates += 1
                        last_status = status
    except Exception as exc:
        error_message = f"callback_parse_error:{exc.__class__.__name__}"
    event_type = "whatsapp.delivery_status"
    InboundWebhookEvent.objects.create(provider="WHATSAPP", event_type=event_type if not last_status else f"{event_type}.{last_status}", signature_valid=bool(signature_valid), payload=payload or {}, matched_message_logs=updates, error_message=error_message)
    return {"updates": updates, "event_type": event_type, "error_message": error_message}


def _invoice_line_sum_subquery():
    from .models import InvoiceLine
    line_total = ExpressionWrapper(F("quantity") * F("unit_amount"), output_field=DecimalField(max_digits=12, decimal_places=2))
    return InvoiceLine.objects.filter(invoice=OuterRef("pk")).annotate(_line_total=line_total).values("invoice").annotate(total=Sum("_line_total")).values("total")[:1]


def _payment_sum_subquery():
    from .models import Payment
    return Payment.objects.filter(invoice=OuterRef("pk")).values("invoice").annotate(total=Sum("amount")).values("total")[:1]


def annotate_invoice_calc_balance(qs):
    return qs.annotate(
        _lines_sum=Coalesce(Subquery(_invoice_line_sum_subquery(), output_field=DecimalField(max_digits=12, decimal_places=2)), Value(Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2))),
        _paid_sum=Coalesce(Subquery(_payment_sum_subquery(), output_field=DecimalField(max_digits=12, decimal_places=2)), Value(Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2))),
    ).annotate(_calc_balance=F("opening_balance") + F("_lines_sum") - F("_paid_sum"))


def filter_invoices_outstanding(qs):
    return annotate_invoice_calc_balance(qs).filter(status="ACTIVE", _calc_balance__gt=0)


def filter_invoices_overdue(qs):
    return annotate_invoice_calc_balance(qs).filter(status="ACTIVE", due_date__lt=timezone.localdate(), _calc_balance__gt=0)


@transaction.atomic
def carry_balance_to_target_term(source_invoice: "Invoice", *, target_year, target_term) -> Tuple["Invoice", str]:
    from .models import Invoice
    if target_term.year_id != target_year.pk:
        raise ValueError("The selected term does not belong to the selected academic year.")
    if source_invoice.academic_term_id == target_term.pk and source_invoice.academic_year_id == target_year.pk:
        raise ValueError("Target term must be different from the source invoice period.")
    balance = source_invoice.balance()
    if balance is None or balance <= Decimal("0"):
        raise ValueError("There is no positive balance to carry forward on this invoice.")
    existing = Invoice.objects.select_for_update().filter(student_id=source_invoice.student_id, academic_year=target_year, academic_term=target_term).exclude(pk=source_invoice.pk).first()
    ref_note = f"B/F inv#{source_invoice.pk}"
    if existing:
        Invoice.objects.filter(pk=existing.pk).update(opening_balance=F("opening_balance") + balance)
        existing.refresh_from_db()
        if ref_note not in (existing.reference or ""):
            existing.reference = f"{existing.reference or ''} {ref_note}".strip()[:64]
            existing.save(update_fields=["reference"])
        return existing, "updated"
    return Invoice.objects.create(student=source_invoice.student, academic_year=target_year, academic_term=target_term, opening_balance=balance, reference=ref_note[:64], status=Invoice.ACTIVE), "created"


def clone_invoice_to_new_period(source_invoice: "Invoice", *, target_year, target_term):
    from .models import Invoice, InvoiceLine
    if target_term.year_id != target_year.pk:
        raise ValueError("The selected term does not belong to the selected academic year.")
    if source_invoice.academic_term_id == target_term.pk and source_invoice.academic_year_id == target_year.pk:
        raise ValueError("Target term must be different from the source invoice period.")
    inv = Invoice.objects.create(student=source_invoice.student, academic_year=target_year, academic_term=target_term, reference=f"Clone inv#{source_invoice.pk}"[:64], opening_balance=Decimal("0"), status=Invoice.ACTIVE)
    for line in source_invoice.lines.all():
        InvoiceLine.objects.create(invoice=inv, fee_item=line.fee_item, description=line.description, quantity=line.quantity, unit_amount=line.unit_amount)
    return inv


def bulk_carry_balances_for_term(*, source_term_id: int, target_year_id: int, target_term_id: int, dry_run: bool = False) -> dict:
    from apps.tenant.academics.models import AcademicTerm, AcademicYear
    from .models import Invoice
    target_year = AcademicYear.objects.get(pk=target_year_id)
    target_term = AcademicTerm.objects.get(pk=target_term_id)
    if target_term.year_id != target_year.pk:
        raise ValueError("Target term must belong to the target academic year.")
    if source_term_id == target_term_id:
        raise ValueError("Source and target terms must be different.")
    summary = {"created": 0, "updated": 0, "would_create": 0, "would_update": 0, "skipped_no_balance": 0, "errors": []}
    invoices = Invoice.objects.filter(academic_term_id=source_term_id).select_related("student").prefetch_related("lines", "payments")
    for invoice in invoices:
        try:
            if invoice.balance() <= 0:
                summary["skipped_no_balance"] += 1
                continue
            existing = Invoice.objects.filter(student=invoice.student, academic_year=target_year, academic_term=target_term).exclude(pk=invoice.pk).exists()
            if dry_run:
                summary["would_update" if existing else "would_create"] += 1
            else:
                _, action = carry_balance_to_target_term(invoice, target_year=target_year, target_term=target_term)
                summary[action] += 1
        except Exception as exc:
            summary["errors"].append({"invoice_id": invoice.pk, "error": str(exc)})
    return summary
