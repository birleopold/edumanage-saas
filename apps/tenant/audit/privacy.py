import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.tenant.portals.role_navigation import portal_base_template_for, portal_home_url_for

from .models import ConsentRecord
from .services import client_ip, user_agent


logger = logging.getLogger(__name__)


def _safe_return_url(request, candidate: object) -> str:
    value = str(candidate or "").strip()
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return portal_home_url_for(request.user)


def _privacy_accept_path() -> str:
    return reverse("audit_privacy_accept")


def _exempt_paths() -> tuple[str, ...]:
    return (
        _privacy_accept_path(),
        reverse("logout"),
        f"/{settings.STATIC_URL.lstrip('/')}",
        f"/{settings.MEDIA_URL.lstrip('/')}",
        "/api/",
        "/health/",
    )


class PrivacyAcceptanceGuard:
    """Require the current privacy version without trapping users in a loop."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, "user", None)
            if user and user.is_authenticated and getattr(settings, "PRIVACY_ACCEPTANCE_REQUIRED", False):
                if not any(request.path.startswith(path) for path in _exempt_paths()):
                    version = getattr(settings, "PRIVACY_POLICY_VERSION", "1.0")
                    accepted = ConsentRecord.objects.filter(
                        user=user,
                        consent_type=ConsentRecord.PRIVACY,
                        accepted=True,
                        version=version,
                    ).exists()
                    if not accepted:
                        query = urlencode({"next": request.get_full_path()})
                        return redirect(f"{_privacy_accept_path()}?{query}")
        except Exception:
            # Fail open so a storage or route fault cannot lock every tenant user out.
            logger.exception("Privacy acceptance guard failed open")
        return self.get_response(request)


@login_required
def accept_privacy(request):
    version = getattr(settings, "PRIVACY_POLICY_VERSION", "1.0")
    requested_return = request.POST.get("next") or request.GET.get("next")

    if request.method == "POST":
        values = {
            "accepted": True,
            "ip_address": client_ip(request),
            "user_agent": user_agent(request),
            "note": "Accepted privacy policy in portal",
        }
        record = (
            ConsentRecord.objects.filter(
                user=request.user,
                consent_type=ConsentRecord.PRIVACY,
                version=version,
            )
            .order_by("-recorded_at")
            .first()
        )
        if record:
            for field, value in values.items():
                setattr(record, field, value)
            record.recorded_at = timezone.now()
            record.save(update_fields=[*values.keys(), "recorded_at"])
        else:
            ConsentRecord.objects.create(
                user=request.user,
                consent_type=ConsentRecord.PRIVACY,
                version=version,
                **values,
            )
        messages.success(request, "Privacy policy accepted.")
        return redirect(_safe_return_url(request, requested_return))

    return render(
        request,
        "portals/audit/privacy_accept.html",
        {
            "version": version,
            "next": _safe_return_url(request, requested_return),
            "base_template": portal_base_template_for(request.user),
        },
    )
