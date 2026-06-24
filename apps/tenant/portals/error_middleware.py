"""Friendly tenant/domain error middleware.

This middleware keeps production users away from raw technical error pages for
common SaaS boundary problems such as suspended tenants and unknown domains.
"""

from django.core.exceptions import DisallowedHost, PermissionDenied, SuspiciousOperation
from django.http import Http404

from . import error_handlers


class ProfessionalErrorMiddleware:
    """Render polished pages for tenant access and domain-resolution problems."""

    ignored_prefixes = ("/static/", "/media/", "/favicon.ico")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except DisallowedHost:
            return error_handlers.invalid_domain(request)
        except SuspiciousOperation as exc:
            if self._looks_like_domain_error(exc):
                return error_handlers.invalid_domain(request)
            return error_handlers.handler400(request, exc)
        except Http404 as exc:
            if self._looks_like_domain_error(exc):
                return error_handlers.invalid_domain(request)
            raise
        except PermissionDenied as exc:
            return error_handlers.handler403(request, exc)

        if self._should_skip(request):
            return response
        tenant = getattr(request, "tenant", None)
        tenant_status = (getattr(tenant, "status", "") or "").lower()
        if tenant and tenant_status == "suspended":
            return error_handlers.tenant_suspended(request)
        return response

    def _should_skip(self, request):
        path = getattr(request, "path", "") or ""
        return any(path.startswith(prefix) for prefix in self.ignored_prefixes)

    def _looks_like_domain_error(self, exc):
        name = exc.__class__.__name__.lower()
        message = str(exc).lower()
        return any(
            marker in name or marker in message
            for marker in (
                "tenant",
                "domain",
                "hostname",
                "host name",
                "host",
                "schema",
                "invalid domain",
            )
        )
