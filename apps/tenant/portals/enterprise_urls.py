from django.urls import path

from . import enterprise_views

urlpatterns = [
    path("", enterprise_views.enterprise_center, name="admin_enterprise_center"),
    path("analytics/", enterprise_views.analytics_center, name="admin_enterprise_analytics"),
    path("audit-security/", enterprise_views.audit_security_center, name="admin_enterprise_audit_security"),
    path("accounting/", enterprise_views.accounting_center, name="admin_enterprise_accounting"),
    path("library/", enterprise_views.library_center, name="admin_enterprise_library"),
    path("org-settings/", enterprise_views.orgsettings_center, name="admin_enterprise_orgsettings"),
    path("permissions/", enterprise_views.permissions_center, name="admin_enterprise_permissions"),
    path("menu/", enterprise_views.menu_registry_view, name="admin_enterprise_menu_registry"),
    path("ui-components/", enterprise_views.ui_components_view, name="admin_enterprise_ui_components"),
]
