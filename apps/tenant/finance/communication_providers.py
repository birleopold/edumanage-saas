import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import send_mail


class ProviderNotConfigured(Exception):
    pass


def _setting(name, default=""):
    return getattr(settings, name, default)


def send_sms_gateway(phone, message, channel="SMS"):
    url = _setting("SMS_GATEWAY_URL")
    token = _setting("SMS_GATEWAY_TOKEN")
    sender_id = _setting("SMS_GATEWAY_SENDER_ID", "EduManage")
    if not url or not token:
        raise ProviderNotConfigured("SMS gateway is not configured.")
    payload = json.dumps({"to": phone, "message": message, "sender_id": sender_id}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="POST")
    with urllib.request.urlopen(req, timeout=_setting("SMS_GATEWAY_TIMEOUT_SECONDS", 15)) as response:
        body = response.read().decode("utf-8")
        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError:
            data = {"raw": body}
        data["status_code"] = response.status
        data["id"] = data.get("id") or data.get("message_id") or data.get("reference") or ""
        return data if 200 <= response.status < 300 else False


def send_whatsapp_cloud(phone, message, channel="WHATSAPP"):
    token = _setting("WHATSAPP_CLOUD_ACCESS_TOKEN")
    phone_id = _setting("WHATSAPP_CLOUD_PHONE_NUMBER_ID")
    version = _setting("WHATSAPP_CLOUD_API_VERSION", "v20.0")
    if not token or not phone_id:
        raise ProviderNotConfigured("WhatsApp Cloud API is not configured.")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    payload = json.dumps({"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"preview_url": False, "body": message}}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="POST")
    with urllib.request.urlopen(req, timeout=_setting("WHATSAPP_CLOUD_TIMEOUT_SECONDS", 15)) as response:
        data = json.loads(response.read().decode("utf-8") or "{}")
        return data if 200 <= response.status < 300 else False


def send_fee_message_provider(phone, message, channel="SMS"):
    channel = (channel or "SMS").upper()
    if channel == "WHATSAPP":
        return send_whatsapp_cloud(phone, message, channel=channel)
    return send_sms_gateway(phone, message, channel=channel)


def send_email_notice(to_email, subject, body):
    if not to_email:
        return {"ok": False, "error": "missing email"}
    sent = send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@edumanage.local"), [to_email], fail_silently=False)
    return {"ok": bool(sent), "sent_count": sent}
