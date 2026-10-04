from django.shortcuts import redirect


class PlatformDjangoAdminGuard:
    """Protect the public-schema Django admin behind owner auth + Platform 2FA."""

    PREFIX = "/dj-admin/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.PREFIX):
            return self.get_response(request)
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return redirect("/platform/login/?next=/dj-admin/")
        if not user.is_superuser:
            return redirect("platform_access_denied")
        if not request.session.get("platform_2fa_verified"):
            request.session["platform_2fa_next"] = request.get_full_path()
            return redirect("platform_verify_2fa")
        return self.get_response(request)
