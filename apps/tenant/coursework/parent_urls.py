from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.coursework_home, name="parent_coursework_home"),
    path("student/<int:student_id>/materials/<int:pk>/", parent_views.material_detail, name="parent_coursework_material_detail"),
    path("student/<int:student_id>/assignments/<int:pk>/", parent_views.assignment_detail, name="parent_coursework_assignment_detail"),
]
