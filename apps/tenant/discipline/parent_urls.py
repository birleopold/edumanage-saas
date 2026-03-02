from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.child_incidents, name="parent_incidents_list"),
]
