"""Backward-compatible push helper for portal notifications.

EduManage now uses the Django PWA/browser push path for normal portal alerts.
This module keeps the old import path working while routing delivery through
web push.
"""

from apps.tenant.portals.push_delivery import send_web_push_to_user


def send_push_to_user(user, *, title: str, body: str, data=None) -> dict:
    url = "/"
    if isinstance(data, dict):
        url = data.get("url") or data.get("href") or url
    result = send_web_push_to_user(user, title=title, body=body, url=url)
    return {**result, "sent_to": result.get("attempted", 0)}
