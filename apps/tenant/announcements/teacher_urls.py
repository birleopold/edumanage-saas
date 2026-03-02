from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.announcement_list, name="teacher_announcements_list"),
]
