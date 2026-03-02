from django.urls import path

from . import admin_views

urlpatterns = [
    path("periods/", admin_views.period_list, name="admin_periods_list"),
    path("periods/create/", admin_views.period_create, name="admin_periods_create"),
    path("periods/<int:pk>/edit/", admin_views.period_edit, name="admin_periods_edit"),

    path("rooms/", admin_views.room_list, name="admin_rooms_list"),
    path("rooms/create/", admin_views.room_create, name="admin_rooms_create"),
    path("rooms/<int:pk>/edit/", admin_views.room_edit, name="admin_rooms_edit"),

    path("entries/", admin_views.entry_list, name="admin_timetable_entries_list"),
    path("entries/create/", admin_views.entry_create, name="admin_timetable_entries_create"),
    path("entries/<int:pk>/edit/", admin_views.entry_edit, name="admin_timetable_entries_edit"),
]
