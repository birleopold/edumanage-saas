from django.urls import path

from . import admin_views, advanced_views

urlpatterns = [
    path("scheduled/run/", admin_views.scheduled_report_run_now, name="admin_reports_scheduled_run"),
    path("scheduled/", admin_views.scheduled_reports, name="admin_reports_scheduled"),
    path("runs/<int:pk>/download/", admin_views.report_run_download, name="admin_reports_run_download"),
    path("overview.csv", admin_views.overview_csv, name="admin_reports_overview_csv"),
    path("finance.csv", admin_views.finance_csv, name="admin_reports_finance_csv"),
    path("attendance.csv", admin_views.attendance_csv, name="admin_reports_attendance_csv"),
    path("academic-performance.csv", admin_views.academic_performance_csv, name="admin_reports_academic_performance_csv"),
    path("advanced/<slug:report_key>.csv", advanced_views.advanced_report_csv, name="admin_reports_advanced_csv"),
    path("advanced/<slug:report_key>/", advanced_views.advanced_report_detail, name="admin_reports_advanced_detail"),
    path("advanced/", advanced_views.advanced_reports_home, name="admin_reports_advanced_home"),
    path("finance/", admin_views.finance_report_view, name="admin_reports_finance"),
    path("attendance/", admin_views.attendance_report_view, name="admin_reports_attendance"),
    path("academic-performance/", admin_views.academic_performance_report_view, name="admin_reports_academic_performance"),
    path("", admin_views.overview, name="admin_reports_overview"),
]