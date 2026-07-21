from django.urls import path

from . import admin_views, grading_views

urlpatterns = [
    path("", admin_views.assessment_list, name="admin_assessments_list"),
    path("create/", admin_views.assessment_create, name="admin_assessments_create"),
    path("tabulation/", admin_views.assessment_tabulation, name="admin_assessments_tabulation"),
    path("framework/", admin_views.assessment_framework_dashboard, name="admin_assessment_framework_dashboard"),
    path("grading/", grading_views.grading_framework_dashboard, name="admin_grading_framework_dashboard"),
    path("grading/profiles/create/", grading_views.grading_profile_create, name="admin_grading_profile_create"),
    path("grading/profiles/<int:pk>/edit/", grading_views.grading_profile_edit, name="admin_grading_profile_edit"),
    path("grading/profiles/<int:profile_pk>/report-rules/", grading_views.report_rule_edit, name="admin_report_rule_edit"),
    path("framework/types/create/", admin_views.assessment_type_create, name="admin_assessment_type_create"),
    path("framework/types/<int:pk>/edit/", admin_views.assessment_type_edit, name="admin_assessment_type_edit"),
    path("framework/schemes/create/", admin_views.weighting_scheme_create, name="admin_weighting_scheme_create"),
    path("framework/schemes/<int:pk>/", admin_views.weighting_scheme_detail, name="admin_weighting_scheme_detail"),
    path("framework/schemes/<int:pk>/edit/", admin_views.weighting_scheme_edit, name="admin_weighting_scheme_edit"),
    path("framework/schemes/<int:scheme_pk>/components/create/", admin_views.weighting_component_create, name="admin_weighting_component_create"),
    path("framework/components/<int:pk>/edit/", admin_views.weighting_component_edit, name="admin_weighting_component_edit"),
    path("<int:pk>/edit/", admin_views.assessment_edit, name="admin_assessments_edit"),
    path("<int:pk>/scores/", admin_views.assessment_scores, name="admin_assessments_scores"),
]
