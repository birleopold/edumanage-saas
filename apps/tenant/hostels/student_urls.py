from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_hostel, name="student_hostel_home"),
]
