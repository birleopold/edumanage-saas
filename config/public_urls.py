from django.urls import include, path

from apps.public.tenants import seo_views, views
from apps.tenant.portals import error_handlers
from apps.tenant.portals.pwa import manifest, push_readiness, service_worker

urlpatterns = [
    path("robots.txt", seo_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", seo_views.sitemap_xml, name="sitemap_xml"),
    path("features/", seo_views.marketing_page, {"page_key": "features"}, name="marketing_features"),
    path(
        "school-management-software/",
        seo_views.marketing_page,
        {"page_key": "school_software"},
        name="marketing_school_software",
    ),
    path("pricing/", seo_views.marketing_page, {"page_key": "pricing"}, name="marketing_pricing"),
    path("contact/", seo_views.marketing_page, {"page_key": "contact"}, name="marketing_contact"),
    path("privacy/", seo_views.marketing_page, {"page_key": "privacy"}, name="marketing_privacy"),
    path("terms/", seo_views.marketing_page, {"page_key": "terms"}, name="marketing_terms"),
    path("health/", views.health, name="health"),
    path("manifest.webmanifest", manifest, name="pwa_manifest"),
    path("service-worker.js", service_worker, name="pwa_service_worker"),
    path("pwa/push-readiness/", push_readiness, name="pwa_push_readiness"),
    path("platform/", include("apps.public.tenants.platform_urls")),
    path("system-unavailable/", error_handlers.system_unavailable, name="system_unavailable"),
    path("tenant-suspended/", error_handlers.tenant_suspended, name="tenant_suspended"),
    path("invalid-domain/", error_handlers.invalid_domain, name="invalid_domain"),
    path("", seo_views.marketing_home, name="marketing_home"),
]

handler400 = error_handlers.handler400
handler404 = error_handlers.handler404
handler500 = error_handlers.handler500
handler403 = error_handlers.handler403
