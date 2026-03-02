from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.results, name="student_exam_results"),
]
