from django.urls import path

from . import online_teacher_views, teacher_views

urlpatterns = [
    path("", teacher_views.home, name="teacher_exams_home"),
    path("papers/<int:pk>/grade/", teacher_views.paper_grade, name="teacher_exam_paper_grade"),
    path("papers/<int:pk>/online-attempts/", online_teacher_views.paper_online_attempts, name="teacher_exam_online_attempts"),
    path("attempts/<int:pk>/mark/", online_teacher_views.online_attempt_mark, name="teacher_exam_attempt_mark"),
]
