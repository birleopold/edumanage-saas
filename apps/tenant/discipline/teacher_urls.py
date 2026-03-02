from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.my_incidents, name="teacher_incidents_list"),
    path("report/", teacher_views.report_incident, name="teacher_incidents_report"),
]
