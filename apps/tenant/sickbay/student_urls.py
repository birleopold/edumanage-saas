from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_sickbay_visits, name="student_sickbay_visits"),
]
