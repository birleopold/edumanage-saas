from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.organization_edit, name="admin_orgsettings_org"),
    path("campuses/", admin_views.campus_list, name="admin_orgsettings_campuses"),
    path("campuses/create/", admin_views.campus_create, name="admin_orgsettings_campus_create"),
    path("campuses/<int:pk>/edit/", admin_views.campus_edit, name="admin_orgsettings_campus_edit"),
    path("campuses/<int:pk>/select/", admin_views.campus_select, name="admin_orgsettings_campus_select"),
    path("feature-flags/", admin_views.feature_flags, name="admin_orgsettings_flags"),
]
