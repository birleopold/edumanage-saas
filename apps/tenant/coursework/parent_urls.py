from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.coursework_home, name="parent_coursework_home"),
    path("student/<int:student_id>/assignments/<int:pk>/", parent_views.assignment_detail, name="parent_coursework_assignment_detail"),
]
