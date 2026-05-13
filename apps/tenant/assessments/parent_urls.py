from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.results_home, name="parent_results_home"),
]
