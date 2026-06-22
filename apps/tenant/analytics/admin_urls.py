from django.urls import include, path

from . import admin_views, record_views

urlpatterns = [
    path("intelligence/", include("apps.tenant.analytics.intelligence_urls")),
    path("records/", record_views.analytics_records_setup, name="admin_analytics_records_setup"),
    path("records/<slug:slug>/", record_views.analytics_records_list, name="admin_analytics_records_list"),
    path("records/<slug:slug>/add/", record_views.analytics_records_create, name="admin_analytics_records_create"),
    path("records/<slug:slug>/<int:pk>/edit/", record_views.analytics_records_edit, name="admin_analytics_records_edit"),
    path("charts/", admin_views.charts_overview, name="admin_analytics_charts"),
    path("api/charts-overview/", admin_views.charts_overview_data, name="admin_analytics_api_charts_overview"),
    path("", admin_views.analytics_dashboard, name="admin_analytics_dashboard"),
    path("students/", admin_views.student_performance_list, name="admin_analytics_student_list"),
    path("students/<int:student_id>/", admin_views.student_performance_detail, name="admin_analytics_student_detail"),
    path("classes/<int:stream_id>/", admin_views.class_performance_report_view, name="admin_analytics_class_report"),
    path("alerts/", admin_views.at_risk_alerts_list, name="admin_analytics_alerts_list"),
    path("alerts/<int:alert_id>/", admin_views.at_risk_alert_detail, name="admin_analytics_alert_detail"),
    path("teachers/", admin_views.teacher_performance_metrics_view, name="admin_analytics_teacher_metrics"),
    path("generate-snapshots/", admin_views.generate_snapshots_bulk, name="admin_analytics_generate_snapshots"),
    path("api/trends/<int:student_id>/", admin_views.performance_trends_chart_data, name="admin_analytics_api_trends"),
    path("api/subject-performance/<int:student_id>/<int:term_id>/", admin_views.subject_performance_chart_data, name="admin_analytics_api_subject"),
    path("api/class-performance/<int:stream_id>/<int:term_id>/", admin_views.class_performance_chart_data, name="admin_analytics_api_class"),
]
