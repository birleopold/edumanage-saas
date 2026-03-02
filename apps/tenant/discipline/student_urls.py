from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_incidents, name="student_incidents_list"),
]
