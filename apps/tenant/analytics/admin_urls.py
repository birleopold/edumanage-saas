from django.urls import path

from . import admin_views

urlpatterns = [
    path("charts/", admin_views.charts_overview, name="admin_analytics_charts"),
    path("api/charts-overview/", admin_views.charts_overview_data, name="admin_analytics_api_charts_overview"),
    # Dashboard
    path("", admin_views.analytics_dashboard, name="admin_analytics_dashboard"),
    
    # Student Performance
    path("students/", admin_views.student_performance_list, name="admin_analytics_student_list"),
    path("students/<int:student_id>/", admin_views.student_performance_detail, name="admin_analytics_student_detail"),
    
    # Class Performance
    path("classes/<int:stream_id>/", admin_views.class_performance_report_view, name="admin_analytics_class_report"),
    
    # At-Risk Alerts
    path("alerts/", admin_views.at_risk_alerts_list, name="admin_analytics_alerts_list"),
    path("alerts/<int:alert_id>/", admin_views.at_risk_alert_detail, name="admin_analytics_alert_detail"),
    
    # Teacher Performance
    path("teachers/", admin_views.teacher_performance_metrics_view, name="admin_analytics_teacher_metrics"),
    
    # Bulk Operations
    path("generate-snapshots/", admin_views.generate_snapshots_bulk, name="admin_analytics_generate_snapshots"),
    
    # Chart Data APIs
    path("api/trends/<int:student_id>/", admin_views.performance_trends_chart_data, name="admin_analytics_api_trends"),
    path("api/subject-performance/<int:student_id>/<int:term_id>/", admin_views.subject_performance_chart_data, name="admin_analytics_api_subject"),
    path("api/class-performance/<int:stream_id>/<int:term_id>/", admin_views.class_performance_chart_data, name="admin_analytics_api_class"),
]
