from django.urls import path

from apps.public.tenants import platform_views, views

urlpatterns = [
    path("health/", views.health, name="health"),

    # Platform owner console for public-schema SaaS operations.
    path("platform/login/", platform_views.platform_login, name="platform_admin_login"),
    path("platform/logout/", platform_views.platform_logout, name="platform_admin_logout"),
    path("platform/", platform_views.dashboard, name="platform_dashboard"),
    path("platform/tenants/", platform_views.tenant_list, name="platform_tenant_list"),
    path("platform/tenants/create/", platform_views.tenant_create, name="platform_tenant_create"),
    path("platform/tenants/<int:pk>/", platform_views.tenant_detail, name="platform_tenant_detail"),
    path("platform/tenants/<int:pk>/edit/", platform_views.tenant_edit, name="platform_tenant_edit"),
    path("platform/tenants/<int:pk>/status/", platform_views.tenant_status_update, name="platform_tenant_status_update"),
    path("platform/tenants/<int:tenant_id>/domains/add/", platform_views.domain_create, name="platform_domain_create"),
    path("platform/domains/<int:pk>/edit/", platform_views.domain_edit, name="platform_domain_edit"),
    path("platform/domains/<int:pk>/primary/", platform_views.domain_mark_primary, name="platform_domain_mark_primary"),
    path("platform/domains/<int:pk>/verify/", platform_views.domain_verify, name="platform_domain_verify"),
    path("platform/domains/<int:pk>/delete/", platform_views.domain_delete, name="platform_domain_delete"),
]
