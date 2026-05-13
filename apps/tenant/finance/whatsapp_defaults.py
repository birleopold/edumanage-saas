"""
Optional WhatsApp handlers for fee reminders.

Example in settings:
    FEE_REMINDER_CHANNEL = "WHATSAPP"
    FEE_REMINDER_HANDLER = "apps.tenant.finance.whatsapp_defaults.send_fee_reminder_whatsapp_cloud_api"
"""
from __future__ import annotations

import json
import logging
from urllib import error, request

from django.conf import settings

logger = logging.getLogger("edumanage.finance.whatsapp")


def log_fee_reminder_whatsapp_to_logger(phone: str, message: str, channel: str = "WHATSAPP") -> bool:
    """Development-friendly handler: logs payload and returns True."""
    logger.info(
        "Fee reminder channel=%s to=%s message=%s",
        channel,
        phone,
        (message or "")[:400],
    )
    return True


def send_fee_reminder_whatsapp_cloud_api(phone: str, message: str, channel: str = "WHATSAPP"):
    """
    Send reminder through WhatsApp Cloud API.

    Required settings:
    - WHATSAPP_CLOUD_ACCESS_TOKEN
    - WHATSAPP_CLOUD_PHONE_NUMBER_ID
    Optional settings:
    - WHATSAPP_CLOUD_API_VERSION (default v20.0)
    - WHATSAPP_CLOUD_TIMEOUT_SECONDS (default 15)
    """
    if channel != "WHATSAPP":
        logger.warning("WhatsApp handler called with non-whatsapp channel=%s", channel)
        return {"ok": False, "error": f"invalid channel {channel}"}

    token = (getattr(settings, "WHATSAPP_CLOUD_ACCESS_TOKEN", "") or "").strip()
    phone_number_id = (getattr(settings, "WHATSAPP_CLOUD_PHONE_NUMBER_ID", "") or "").strip()
    api_version = (getattr(settings, "WHATSAPP_CLOUD_API_VERSION", "v20.0") or "v20.0").strip()
    timeout = int(getattr(settings, "WHATSAPP_CLOUD_TIMEOUT_SECONDS", 15) or 15)

    if not token or not phone_number_id:
        logger.warning("WhatsApp Cloud settings missing token or phone number ID")
        return {"ok": False, "error": "missing WhatsApp Cloud settings"}

    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message,
        },
    }
    payload = json.dumps(body).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            body_raw = resp.read()
            body = {}
            if body_raw:
                try:
                    body = json.loads(body_raw.decode("utf-8"))
                except Exception:
                    body = {}
            if 200 <= int(code) < 300:
                return body or {"ok": True}
            logger.warning("WhatsApp Cloud non-2xx status=%s", code)
            return {"ok": False, "status": code, "response": body}
    except error.HTTPError as exc:
        logger.warning("WhatsApp Cloud HTTP error status=%s", getattr(exc, "code", "unknown"))
        return {"ok": False, "status": getattr(exc, "code", None), "error": "http_error"}
    except error.URLError as exc:
        logger.warning("WhatsApp Cloud URL error reason=%s", getattr(exc, "reason", "unknown"))
        return {"ok": False, "error": f"url_error:{getattr(exc, 'reason', 'unknown')}"}
    except Exception:
        logger.exception("WhatsApp Cloud send failed")
        return {"ok": False, "error": "exception"}
