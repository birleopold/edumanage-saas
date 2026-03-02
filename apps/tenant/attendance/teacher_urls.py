from django.urls import path

from . import teacher_views
from . import teacher_views_rollcall

urlpatterns = [
    path("", teacher_views.attendance_home, name="teacher_attendance_home"),
    path("take/", teacher_views.attendance_take, name="teacher_attendance_take"),
    path("roll-call/", teacher_views_rollcall.roll_call, name="teacher_roll_call"),
    path("roll-call/save/", teacher_views_rollcall.roll_call_save, name="teacher_roll_call_save"),
    path("roll-call/mark/", teacher_views_rollcall.roll_call_mark_student, name="teacher_roll_call_mark"),
]
