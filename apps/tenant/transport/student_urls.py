from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_transport, name="student_transport_home"),
    path("assignments/<int:pk>/", student_views.transport_detail, name="student_transport_assignment_detail"),
]
