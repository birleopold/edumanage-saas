"""Unauthenticated public pages (status, health summaries)."""

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def public_status(request):
    """
    Simple trust / NOC page: confirms the app responds and high-level messaging readiness.
    Never exposes secrets (tokens, keys). JSON with ?format=json or Accept: application/json.
    """
    if not getattr(settings, "PUBLIC_STATUS_PAGE_ENABLED", True):
        raise Http404

    from apps.tenant.finance.services import messaging_readiness_snapshot

    snap = messaging_readiness_snapshot(sample_limit=3)
    payload = {
        "ok": True,
        "time": timezone.now().isoformat(),
        "web": "up",
        "fee_messaging": {
            "channel": snap.get("channel"),
            "handler_ready": bool(snap.get("handler_resolved")),
            "whatsapp_credentials_present": bool(
                snap.get("whatsapp_token_set") and snap.get("whatsapp_phone_number_id_set")
            ),
            "parent_portal_base_configured": bool(snap.get("portal_base_configured")),
            "failed_message_logs_total": snap.get("failed_logs_count"),
        },
    }

    want_json = request.GET.get("format") == "json" or "application/json" in (
        request.headers.get("Accept") or ""
    )
    if want_json:
        return JsonResponse(payload)
    return render(request, "public/status.html", {"payload": payload})
