from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.attendance_home, name="student_attendance_home"),
]
