from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.incident_list, name="admin_incidents_list"),
    path("create/", admin_views.incident_create, name="admin_incidents_create"),
    path("<int:pk>/", admin_views.incident_detail, name="admin_incidents_detail"),
    path("<int:pk>/edit/", admin_views.incident_edit, name="admin_incidents_edit"),
]
