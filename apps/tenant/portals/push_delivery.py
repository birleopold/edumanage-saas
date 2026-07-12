"""Optional Python-only web push delivery helpers.

This keeps EduManage PWA push support independent of Node/npm. If the Python
`pywebpush` package is installed and VAPID keys are configured, this helper can
send notifications to saved browser subscriptions. Without that package, the
subscription storage still works and the function returns a clear skipped result.
"""

import json

from decouple import config
from django.utils import timezone

from .models import WebPushSubscription


class WebPushNotConfigured(RuntimeError):
    pass


def _vapid_claims():
    private_key = config("WEB_PUSH_PRIVATE_KEY", default="").replace("\\n", "\n")
    subject = config("WEB_PUSH_SUBJECT", default="mailto:support@edumanage.local")
    if not private_key:
        raise WebPushNotConfigured("WEB_PUSH_PRIVATE_KEY is not configured.")
    return {"sub": subject}, private_key


def send_web_push(subscription: WebPushSubscription, *, title: str, body: str, url: str = "/") -> dict:
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return {"ok": False, "skipped": True, "reason": "Install the Python package pywebpush to enable delivery."}

    try:
        claims, private_key = _vapid_claims()
    except WebPushNotConfigured as exc:
        return {"ok": False, "skipped": True, "reason": str(exc)}
    payload = json.dumps({"title": title, "body": body, "url": url})
    info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
    }
    try:
        webpush(subscription_info=info, data=payload, vapid_private_key=private_key, vapid_claims=claims)
    except WebPushException as exc:
        subscription.last_error = str(exc)
        subscription.is_active = getattr(exc, "response", None) is None or getattr(exc.response, "status_code", 0) not in (404, 410)
        subscription.save(update_fields=["last_error", "is_active", "updated_at"])
        return {"ok": False, "skipped": False, "reason": str(exc)}

    subscription.last_success_at = timezone.now()
    subscription.last_error = ""
    subscription.is_active = True
    subscription.save(update_fields=["last_success_at", "last_error", "is_active", "updated_at"])
    return {"ok": True, "skipped": False}


def send_web_push_to_user(user, *, title: str, body: str, url: str = "/") -> dict:
    results = []
    subscriptions = (
        WebPushSubscription.objects.filter(user=user, is_active=True)
        .exclude(p256dh_key="")
        .exclude(auth_key="")
    )
    for subscription in subscriptions:
        results.append(send_web_push(subscription, title=title, body=body, url=url))
    return {"sent": sum(1 for item in results if item.get("ok")), "attempted": len(results), "results": results}
