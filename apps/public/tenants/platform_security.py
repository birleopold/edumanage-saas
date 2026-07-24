"""Security headers and CSRF freshness for the public platform console."""

from django.middleware.csrf import get_token
from django.utils.cache import patch_cache_control


class PlatformFormSecurityMiddleware:
    """Keep platform forms private, uncached and paired with a fresh CSRF cookie.

    The platform console contains administrative forms whose HTML must never be
    reused by a browser, reverse proxy or service worker after the CSRF cookie
    changes. Calling ``get_token`` during safe platform requests asks Django's
    CSRF middleware to refresh the cookie on the outgoing response.
    """

    PLATFORM_PREFIX = "/platform/"
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_platform_request = request.path.startswith(self.PLATFORM_PREFIX)

        if is_platform_request and request.method in self.SAFE_METHODS:
            get_token(request)

        response = self.get_response(request)

        if is_platform_request:
            patch_cache_control(
                response,
                private=True,
                no_cache=True,
                no_store=True,
                must_revalidate=True,
                max_age=0,
            )
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
