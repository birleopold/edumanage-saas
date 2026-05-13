from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.announcement_list, name="admin_announcements_list"),
    path("create/", admin_views.announcement_create, name="admin_announcements_create"),
    path("<int:pk>/edit/", admin_views.announcement_edit, name="admin_announcements_edit"),
    path("<int:pk>/broadcast/", admin_views.announcement_broadcast, name="admin_announcements_broadcast"),
]
