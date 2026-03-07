from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.activity_list, name="admin_activities_list"),
    path("create/", admin_views.activity_create, name="admin_activities_create"),
    path("<int:pk>/edit/", admin_views.activity_edit, name="admin_activities_edit"),
    path("<int:pk>/members/", admin_views.activity_members, name="admin_activities_members"),
    path("<int:pk>/members/add/", admin_views.activity_member_add, name="admin_activities_member_add"),
    path(
        "<int:pk>/members/<int:member_id>/remove/",
        admin_views.activity_member_remove,
        name="admin_activities_member_remove",
    ),
]
