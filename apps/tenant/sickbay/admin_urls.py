from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.sickbay_dashboard, name="admin_sickbay_dashboard"),
    path("visits/", admin_views.visit_list, name="admin_sickbay_visit_list"),
    path("visits/create/", admin_views.visit_create, name="admin_sickbay_visit_create"),
    path("visits/<int:pk>/", admin_views.visit_detail, name="admin_sickbay_visit_detail"),
    path("visits/<int:pk>/edit/", admin_views.visit_edit, name="admin_sickbay_visit_edit"),
    path("profiles/", admin_views.medical_profile_list, name="admin_sickbay_profile_list"),
    path("profiles/create/", admin_views.medical_profile_create, name="admin_sickbay_profile_create"),
    path("profiles/<int:pk>/edit/", admin_views.medical_profile_edit, name="admin_sickbay_profile_edit"),
]
