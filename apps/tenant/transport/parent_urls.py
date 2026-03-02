from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.children_transport, name="parent_transport_home"),
]
