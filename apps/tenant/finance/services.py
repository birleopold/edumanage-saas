"""
Finance helpers: money text for SMS/email, balance carry-forward, fee reminder dispatch.
"""
from __future__ import annotations

import logging
import re
import json
import hmac
import hashlib
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from inspect import signature
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
from urllib import error, request

if TYPE_CHECKING:
    from .models import Invoice

from django.conf import settings
from django.db import transaction
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger("edumanage.finance")


def format_money_for_message(amount: Decimal | float | str | None, currency_code: str = "UGX") -> str:
    """Plain-text amount for SMS or email (matches template filter behaviour)."""
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
    """
    Optional Django setting FEE_REMINDER_HANDLER (preferred) or legacy FEE_REMINDER_SMS_HANDLER:
    - dotted path to a function (phone: str, message: str) -> bool
    - or a callable set directly on settings (tests).
    """
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
    """
    Normalize phone for WhatsApp Cloud API.

    - Accepts local formats like 07xxxxxxxx and international forms with punctuation.
    - Returns digits only in international format (no plus sign), or empty if invalid.
    """
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
    """
    Build absolute portal invoice URL when FEE_REMINDER_PORTAL_BASE_URL is set.
    Returns empty string when not configured.
    """
    base = (getattr(settings, "FEE_REMINDER_PORTAL_BASE_URL", "") or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/parent/finance/invoices/{invoice.pk}/"


def _extract_provider_message_id(provider_response) -> str:
    if not isinstance(provider_response, dict):
        return ""
    if provider_response.get("messages") and isinstance(provider_response.get("messages"), list):
        first = provider_response["messages"][0] or {}
        if isinstance(first, dict):
            return str(first.get("id") or "")
    return str(provider_response.get("id") or "")


def dispatch_fee_message(phone: str, message: str, *, channel_override: str | None = None) -> dict:
    """
    Dispatch one reminder message using configured channel (SMS or WhatsApp).
    Returns a result dict for logging and UI feedback.
    """
    phone = (phone or "").strip()
    if not phone:
        logger.warning("dispatch_fee_reminder_sms: empty phone")
        return {"ok": False, "phone_normalized": "", "channel": "", "error": "empty phone"}
    configured = _current_channel()
    channel = (channel_override or configured or "SMS").strip().upper()
    normalized_phone = phone
    if channel == "WHATSAPP":
        normalized_phone = normalize_phone_for_whatsapp(
            phone, getattr(settings, "FEE_REMINDER_DEFAULT_COUNTRY_CODE", "256")
        )
        if not normalized_phone:
            logger.warning("dispatch_fee_reminder_sms: invalid whatsapp phone=%s", phone[:12])
            return {
                "ok": False,
                "phone_normalized": "",
                "channel": channel,
                "error": "invalid whatsapp phone",
            }

    handler = _fee_reminder_handler()
    if handler:
        try:
            params = signature(handler).parameters
            if "channel" in params:
                response = handler(normalized_phone, message, channel=channel)
            else:
                response = handler(normalized_phone, message)
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
        except Exception:
            logger.exception("FEE_REMINDER handler failed for phone=%s", normalized_phone[:8])
            return {
                "ok": False,
                "phone_normalized": normalized_phone,
                "channel": channel,
                "provider_response": {},
                "provider_message_id": "",
                "error": "handler exception",
            }
    logger.info(
        "Fee reminder %s (no handler) to=%s msg=%s",
        channel,
        normalized_phone,
        message[:200],
    )
    return {
        "ok": True,
        "phone_normalized": normalized_phone,
        "channel": channel,
        "provider_response": {},
        "provider_message_id": "",
        "error": "",
    }


def dispatch_fee_reminder_sms(phone: str, message: str) -> bool:
    """Backward-compatible boolean dispatch wrapper."""
    return bool(dispatch_fee_message(phone, message).get("ok"))


def parent_phones_for_student(student) -> List[str]:
    """Phone numbers from linked parents (primary first), deduplicated and consent-aware."""
    from apps.tenant.parents.models import ParentStudentLink

    channel = _current_channel()
    phones: List[str] = []
    seen = set()
    links = (
        ParentStudentLink.objects.filter(student=student)
        .select_related("parent")
        .order_by("-is_primary", "parent__last_name")
    )
    for link in links:
        if not _parent_allows_channel(link.parent, channel):
            continue
        p = (link.parent.phone or "").strip()
        if p and p not in seen:
            seen.add(p)
            phones.append(p)
    return phones


# Existing service body intentionally kept below this point by appending generated helpers.
