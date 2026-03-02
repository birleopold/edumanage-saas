from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.overview, name="admin_reports_overview"),
    path("overview.csv", admin_views.overview_csv, name="admin_reports_overview_csv"),
]
