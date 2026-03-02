from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.results_home, name="student_results_home"),
]
