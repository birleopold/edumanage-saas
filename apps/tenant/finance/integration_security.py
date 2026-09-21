from rest_framework.permissions import BasePermission

from .models import IntegrationApiKey, IntegrationApiKeyScope


class HasScopedIntegrationKey(BasePermission):
    message = "Valid X-API-Key with required scope is required."

    def has_permission(self, request, view):
        raw = (request.headers.get("X-API-Key") or "").strip()
        key_obj = IntegrationApiKey.resolve_active_key(raw)
        if not key_obj:
            return False
        client_ip = (request.META.get("REMOTE_ADDR") or "").strip()
        if not key_obj.allows_ip(client_ip):
            return False
        request.integration_api_key = key_obj
        required = getattr(view, "required_scope", "")
        if not required:
            key_obj.mark_used()
            return True
        allowed = IntegrationApiKeyScope.objects.filter(
            api_key=key_obj,
            scope__code__in=(required, "integrations-admin"),
            scope__is_active=True,
        ).exists()
        if allowed:
            key_obj.mark_used()
        return allowed
