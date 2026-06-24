from django.urls import include, path

from apps.public.tenants import views
from apps.tenant.portals import error_handlers

urlpatterns = [
    path("health/", views.health, name="health"),
    path("platform/", include("apps.public.tenants.platform_urls")),
    path("system-unavailable/", error_handlers.system_unavailable, name="system_unavailable"),
    path("tenant-suspended/", error_handlers.tenant_suspended, name="tenant_suspended"),
    path("invalid-domain/", error_handlers.invalid_domain, name="invalid_domain"),
]

handler400 = error_handlers.handler400
handler404 = error_handlers.handler404
handler500 = error_handlers.handler500
handler403 = error_handlers.handler403
