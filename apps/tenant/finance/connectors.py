from django.urls import path

from . import connector_pages, integration_ops

urlpatterns = [
    path("", integration_ops.integrations_center, name="admin_connectors_home"),
    path("tabs/<str:tab>/", integration_ops.integrations_center, name="admin_connectors_tab"),
    path("providers/new/", connector_pages.provider_edit, name="admin_connectors_provider_new"),
    path("providers/<int:pk>/", connector_pages.provider_edit, name="admin_connectors_provider_edit"),
    path("providers/<int:pk>/test/", integration_ops.provider_test, name="admin_connectors_provider_test"),
    path("keys/create/", integration_ops.api_key_create, name="admin_connectors_api_key_create"),
    path("keys/<int:pk>/rotate/", integration_ops.api_key_rotate, name="admin_connectors_api_key_rotate"),
    path("keys/<int:pk>/toggle/", integration_ops.api_key_toggle, name="admin_connectors_api_key_toggle"),
    path("scopes/create/", integration_ops.scope_create, name="admin_connectors_scope_create"),
    path("webhooks/create/", integration_ops.webhook_create, name="admin_connectors_webhook_create"),
    path("webhooks/<int:pk>/test/", integration_ops.webhook_test, name="admin_connectors_webhook_test"),
    path("retries/<int:pk>/now/", integration_ops.retry_queue_now, name="admin_connectors_retry_now"),
]
