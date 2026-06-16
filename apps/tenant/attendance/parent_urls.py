from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.attendance_home, name="parent_attendance_home"),
    path("student/<int:student_id>/", parent_views.student_attendance_detail, name="parent_student_attendance_detail"),
]
