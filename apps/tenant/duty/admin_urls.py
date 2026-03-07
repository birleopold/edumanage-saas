from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.roster_list, name="admin_duty_list"),
    path("create/", admin_views.roster_create, name="admin_duty_create"),
    path("<int:pk>/edit/", admin_views.roster_edit, name="admin_duty_edit"),
]
