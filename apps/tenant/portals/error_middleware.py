"""Friendly tenant/domain error middleware.

This middleware keeps production users away from raw technical error pages for
common SaaS boundary problems such as suspended tenants and unknown domains.
"""

from django.core.exceptions import DisallowedHost, PermissionDenied, SuspiciousOperation
from django.http import Http404

from apps.tenant.audit.request_ids import apply_request_id, ensure_request_id

from . import error_handlers


class ProfessionalErrorMiddleware:
    """Render polished pages for tenant access and domain-resolution problems."""

    ignored_prefixes = ("/static/", "/media/", "/favicon.ico")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ensure_request_id(request)

        try:
            response = self.get_response(request)
        except DisallowedHost:
            response = error_handlers.invalid_domain(request)
        except SuspiciousOperation as exc:
            if self._looks_like_domain_error(exc):
                response = error_handlers.invalid_domain(request)
            else:
                response = error_handlers.handler400(request, exc)
        except Http404 as exc:
            if self._looks_like_domain_error(exc):
                response = error_handlers.invalid_domain(request)
            else:
                raise
        except PermissionDenied as exc:
            response = error_handlers.handler403(request, exc)

        if not self._should_skip(request):
            tenant = getattr(request, "tenant", None)
            tenant_status = (getattr(tenant, "status", "") or "").lower()
            if tenant and tenant_status == "suspended":
                response = error_handlers.tenant_suspended(request)

        return apply_request_id(response, request)

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
