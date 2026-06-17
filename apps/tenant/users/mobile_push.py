import json
import urllib.error
import urllib.request

from django.conf import settings

from .models import MobileDevice


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def expo_push_enabled() -> bool:
    return bool(getattr(settings, "MOBILE_EXPO_PUSH_ENABLED", False))


def send_expo_push_message(*, push_token: str, title: str, body: str, data=None) -> dict:
    if not push_token:
        return {"ok": False, "error": "missing_push_token"}
    if not expo_push_enabled():
        return {"ok": False, "dry_run": True, "provider": "expo", "title": title, "body": body}
    payload = json.dumps({"to": push_token, "title": title, "body": body, "data": data or {}}).encode("utf-8")
    request = urllib.request.Request(EXPO_PUSH_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=getattr(settings, "MOBILE_PUSH_TIMEOUT_SECONDS", 10)) as response:
            return {"ok": 200 <= response.status < 300, "status_code": response.status, "provider_response": json.loads(response.read().decode("utf-8") or "{}")}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc)}


def send_push_to_user(user, *, title: str, body: str, data=None) -> dict:
    devices = MobileDevice.objects.filter(user=user, is_active=True).exclude(push_token="")
    results = [send_expo_push_message(push_token=device.push_token, title=title, body=body, data=data) for device in devices]
    return {"sent_to": len(results), "results": results}
