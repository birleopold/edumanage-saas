from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.assessment_home, name="teacher_assessments_home"),
    path("create/", teacher_views.assessment_create, name="teacher_assessments_create"),
    path("<int:pk>/grade/", teacher_views.assessment_grade, name="teacher_assessments_grade"),
]
