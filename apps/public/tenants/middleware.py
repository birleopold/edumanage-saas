from django.conf import settings
from django.shortcuts import render


DEFAULT_UNAVAILABLE_STATUSES = ("suspended", "archived")
DEFAULT_EXEMPT_PATH_PREFIXES = ("/static/", "/media/", "/health/")


class TenantStatusMiddleware:
    """Return a friendly unavailable page for inactive school tenants."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", "public")
        status = (getattr(tenant, "status", "") or "").lower()

        if tenant and schema_name != "public" and self._is_unavailable(status) and not self._is_exempt(request.path):
            return render(
                request,
                "errors/tenant_unavailable.html",
                {"tenant": tenant, "tenant_status": status},
                status=403,
            )

        return self.get_response(request)

    def _is_unavailable(self, status: str) -> bool:
        unavailable = getattr(settings, "TENANT_STATUS_UNAVAILABLE_STATUSES", DEFAULT_UNAVAILABLE_STATUSES)
        return status in {item.lower() for item in unavailable}

    def _is_exempt(self, path: str) -> bool:
        prefixes = getattr(settings, "TENANT_STATUS_EXEMPT_PATH_PREFIXES", DEFAULT_EXEMPT_PATH_PREFIXES)
        return any(path.startswith(prefix) for prefix in prefixes)
