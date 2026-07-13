from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.child_sickbay_visits, name="parent_sickbay_visits"),
]
