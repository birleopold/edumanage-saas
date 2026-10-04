from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from .models import Domain


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "edumanage",
            "time": timezone.now().isoformat(),
            "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        }
    )


def caddy_domain_permission(request):
    """Authorize Caddy on-demand TLS only for registered, operable tenant domains."""
    domain_name = (request.GET.get("domain") or "").strip().lower().rstrip(".")
    if not domain_name or len(domain_name) > 253:
        return HttpResponse(status=404)
    allowed = Domain.objects.filter(
        domain__iexact=domain_name,
        tenant__status="active",
    ).exists()
    if not allowed:
        return HttpResponse(status=404)
    return HttpResponse("allowed", content_type="text/plain", status=200)


def public_pwa_readiness(request):
    """Public/platform host PWA status without querying tenant-only push tables."""
    return JsonResponse({
        "service_worker": True,
        "push_api_ready": False,
        "vapid_public_key_configured": False,
        "vapid_public_key": "",
        "subscription_storage_ready": False,
        "active_subscriptions": 0,
        "subscribe_url": "",
        "unsubscribe_url": "",
        "private_page_caching": False,
        "message": "Platform PWA shell is available. School push subscriptions are tenant-scoped.",
    })
