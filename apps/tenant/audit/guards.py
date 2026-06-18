from django.shortcuts import redirect

from .twofactor import user_needs_2fa


class AdminTwoFactorGuard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.path.startswith("/admin/") and not request.path.startswith("/admin/security/2fa/"):
                if user_needs_2fa(request.user) and not request.session.get("admin_2fa_verified"):
                    return redirect("audit_verify_2fa")
        except Exception:
            pass
        return self.get_response(request)
