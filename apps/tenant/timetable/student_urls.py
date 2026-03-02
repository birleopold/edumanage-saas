from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_timetable, name="student_timetable"),
]
