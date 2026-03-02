from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.announcement_list, name="student_announcements_list"),
]
