from django.urls import path

from . import admin_views

urlpatterns = [
    path("scheduled/run/", admin_views.scheduled_report_run_now, name="admin_reports_scheduled_run"),
    path("scheduled/", admin_views.scheduled_reports, name="admin_reports_scheduled"),
    path("runs/<int:pk>/download/", admin_views.report_run_download, name="admin_reports_run_download"),
    path("overview.csv", admin_views.overview_csv, name="admin_reports_overview_csv"),
    path("", admin_views.overview, name="admin_reports_overview"),
]
