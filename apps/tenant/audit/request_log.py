from django.conf import settings
from django.shortcuts import redirect

from .models import ConsentRecord
from .services import log_audit
from .twofactor import user_needs_2fa


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, "user", None)
            if user and user.is_authenticated:
                if request.path.startswith("/admin/") and not request.path.startswith("/admin/audit/verify/"):
                    if user_needs_2fa(user) and not request.session.get("admin_2fa_verified"):
                        return redirect("audit_verify_2fa")
                exempt = ["/admin/audit/accept/", "/logout/", "/static/", "/media/", "/api/", "/admin/audit/verify/"]
                if not any(request.path.startswith(x) for x in exempt):
                    version = getattr(settings, "PRIVACY_POLICY_VERSION", "1.0")
                    accepted = ConsentRecord.objects.filter(user=user, consent_type=ConsentRecord.PRIVACY, accepted=True, version=version).exists()
                    if not accepted:
                        return redirect("audit_privacy_accept")
        except Exception:
            pass
        response = self.get_response(request)
        try:
            if not getattr(settings, "AUDIT_LOG_ENABLED", True):
                return response
            if request.path.startswith(settings.STATIC_URL) or request.path.startswith(settings.MEDIA_URL):
                return response
            if getattr(request, "user", None) and request.user.is_authenticated:
                status = getattr(response, "status_code", 200)
                if status < 500:
                    log_audit(request, metadata={"status_code": status, "content_type": response.get("Content-Type", "")})
        except Exception:
            pass
        return response
