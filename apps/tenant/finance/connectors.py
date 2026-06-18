from django.urls import path

from . import connector_pages

urlpatterns = [
    path("", connector_pages.connector_home, name="admin_connectors_home"),
    path("providers/new/", connector_pages.provider_edit, name="admin_connectors_provider_new"),
    path("providers/<int:pk>/", connector_pages.provider_edit, name="admin_connectors_provider_edit"),
]
