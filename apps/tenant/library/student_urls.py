from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.my_loans, name="student_library_loans"),
]
