from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.assessment_list, name="admin_assessments_list"),
    path("create/", admin_views.assessment_create, name="admin_assessments_create"),
    path("<int:pk>/edit/", admin_views.assessment_edit, name="admin_assessments_edit"),
    path("<int:pk>/scores/", admin_views.assessment_scores, name="admin_assessments_scores"),
]
