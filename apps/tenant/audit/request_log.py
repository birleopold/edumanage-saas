from django.conf import settings

from .services import log_audit


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
