from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.children_hostels, name="parent_hostel_home"),
]
