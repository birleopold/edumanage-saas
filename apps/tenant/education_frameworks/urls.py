from django.urls import path

from . import views

urlpatterns = [
    path("", views.framework_dashboard, name="admin_education_framework_dashboard"),
    path("profile/", views.profile_edit, name="admin_education_framework_profile"),
    path("terminology/", views.terminology_edit, name="admin_education_framework_terminology"),
    path("campus-stages/create/", views.campus_stage_create, name="admin_campus_education_stage_create"),
    path("campus-stages/<int:pk>/edit/", views.campus_stage_edit, name="admin_campus_education_stage_edit"),
    path("level-mappings/<int:pk>/edit/", views.mapping_edit, name="admin_level_stage_mapping_edit"),
]
