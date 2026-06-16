from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.results_home, name="student_results_home"),
    path("report-card/", student_views.report_card, name="student_report_card"),
    path("report-card/print/", student_views.report_card_print, name="student_report_card_print"),
]
