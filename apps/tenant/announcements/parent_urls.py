from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.announcement_list, name="parent_announcements_list"),
]
