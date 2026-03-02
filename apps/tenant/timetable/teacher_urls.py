from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.my_timetable, name="teacher_timetable"),
]
