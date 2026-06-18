from django.urls import path

from . import intelligence_views

urlpatterns = [
    path("", intelligence_views.intelligence_dashboard, name="admin_analytics_intelligence"),
    path("alerts/<int:alert_id>/interventions/new/", intelligence_views.intervention_create, name="admin_analytics_intervention_new"),
    path("interventions/<int:pk>/", intelligence_views.intervention_update, name="admin_analytics_intervention_edit"),
    path("api/class-comparison/", intelligence_views.class_comparison_data, name="admin_analytics_api_class_comparison"),
    path("api/attendance-correlation/", intelligence_views.attendance_correlation_data, name="admin_analytics_api_attendance_correlation"),
]
