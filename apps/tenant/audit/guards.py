import logging

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .twofactor import user_needs_2fa


logger = logging.getLogger(__name__)


def _two_factor_exempt_paths() -> tuple[str, ...]:
    return (
        reverse("audit_verify_2fa"),
        reverse("audit_two_factor_settings"),
        reverse("logout"),
        f"/{settings.STATIC_URL.lstrip('/')}",
        f"/{settings.MEDIA_URL.lstrip('/')}",
    )


class AdminTwoFactorGuard:
    """Protect administrator-shell routes without redirecting the OTP page to itself."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, "user", None)
            is_exempt = any(request.path.startswith(path) for path in _two_factor_exempt_paths())
            if (
                user
                and user.is_authenticated
                and request.path.startswith("/admin/")
                and not is_exempt
                and user_needs_2fa(user)
                and not request.session.get("admin_2fa_verified")
            ):
                return redirect("audit_verify_2fa")
        except Exception:
            # Fail open and emit evidence rather than creating a platform-wide loop.
            logger.exception("Administrator two-factor guard failed open")
        return self.get_response(request)
