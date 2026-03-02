from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_transport, name="student_transport_home"),
]
