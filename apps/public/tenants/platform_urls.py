from django.urls import path

from . import platform_views, wizard_views

urlpatterns = [
    path("login/", platform_views.platform_login, name="platform_admin_login"),
    path("logout/", platform_views.platform_logout, name="platform_admin_logout"),
    path("", platform_views.dashboard, name="platform_dashboard"),
    path("activity/", platform_views.platform_activity, name="platform_activity"),
    path("tenants/", platform_views.tenant_list, name="platform_tenant_list"),
    path("tenants/create/", wizard_views.create_school_wizard, name="platform_tenant_create"),
    path("tenants/create/classic/", platform_views.tenant_create, name="platform_tenant_create_classic"),
    path("tenants/<int:pk>/", platform_views.tenant_detail, name="platform_tenant_detail"),
    path("tenants/<int:pk>/edit/", platform_views.tenant_edit, name="platform_tenant_edit"),
    path("tenants/<int:pk>/status/", platform_views.tenant_status_update, name="platform_tenant_status_update"),
    path("tenants/<int:tenant_id>/domains/add/", platform_views.domain_create, name="platform_domain_create"),
    path("domains/<int:pk>/edit/", platform_views.domain_edit, name="platform_domain_edit"),
    path("domains/<int:pk>/primary/", platform_views.domain_mark_primary, name="platform_domain_mark_primary"),
    path("domains/<int:pk>/verify/", platform_views.domain_verify, name="platform_domain_verify"),
    path("domains/<int:pk>/delete/", platform_views.domain_delete, name="platform_domain_delete"),
]