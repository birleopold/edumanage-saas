from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.home, name="teacher_exams_home"),
    path("papers/<int:pk>/grade/", teacher_views.paper_grade, name="teacher_exam_paper_grade"),
]
