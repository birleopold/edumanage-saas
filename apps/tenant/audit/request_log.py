import logging
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect

from .guards import _two_factor_exempt_paths
from .models import ConsentRecord
from .privacy import _exempt_paths, _privacy_accept_path
from .services import log_audit
from .twofactor import user_needs_2fa


logger = logging.getLogger(__name__)


class RequestLogMiddleware:
    """Enforce account gates, then record successful authenticated requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, "user", None)
            if user and user.is_authenticated:
                two_factor_exempt = any(
                    request.path.startswith(path) for path in _two_factor_exempt_paths()
                )
                if (
                    request.path.startswith("/admin/")
                    and not two_factor_exempt
                    and user_needs_2fa(user)
                    and not request.session.get("admin_2fa_verified")
                ):
                    return redirect("audit_verify_2fa")

                privacy_exempt = any(request.path.startswith(path) for path in _exempt_paths())
                if getattr(settings, "PRIVACY_ACCEPTANCE_REQUIRED", False) and not privacy_exempt:
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
            # Authentication gates fail open but leave operational evidence.
            logger.exception("Account gate enforcement failed open")

        response = self.get_response(request)
        try:
            if not getattr(settings, "AUDIT_LOG_ENABLED", True):
                return response
            if request.path.startswith(settings.STATIC_URL) or request.path.startswith(settings.MEDIA_URL):
                return response
            if getattr(request, "user", None) and request.user.is_authenticated:
                status = getattr(response, "status_code", 200)
                if status < 500:
                    log_audit(
                        request,
                        metadata={
                            "status_code": status,
                            "content_type": response.get("Content-Type", ""),
                        },
                    )
        except Exception:
            logger.exception("Request audit logging failed open")
        return response
