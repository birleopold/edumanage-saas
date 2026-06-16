from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.results_home, name="parent_results_home"),
    path("student/<int:student_id>/report-card/", parent_views.report_card, name="parent_report_card"),
    path("student/<int:student_id>/report-card/print/", parent_views.report_card_print, name="parent_report_card_print"),
]
