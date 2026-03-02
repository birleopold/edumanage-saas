from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.children_loans, name="parent_library_loans"),
]
