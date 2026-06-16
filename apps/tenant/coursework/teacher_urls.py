from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.coursework_home, name="teacher_coursework_home"),
    path("materials/create/", teacher_views.material_create, name="teacher_coursework_material_create"),
    path("materials/<int:pk>/", teacher_views.material_detail, name="teacher_coursework_material_detail"),
    path("materials/<int:pk>/edit/", teacher_views.material_edit, name="teacher_coursework_material_edit"),
    path("assignments/create/", teacher_views.assignment_create, name="teacher_coursework_assignment_create"),
    path("assignments/<int:pk>/", teacher_views.assignment_detail, name="teacher_coursework_assignment_detail"),
    path("assignments/<int:pk>/edit/", teacher_views.assignment_edit, name="teacher_coursework_assignment_edit"),
    path("assignments/<int:pk>/submissions/", teacher_views.assignment_submissions, name="teacher_coursework_assignment_submissions"),
    path("assignments/<int:assignment_id>/submissions/<int:submission_id>/mark/", teacher_views.submission_mark, name="teacher_coursework_submission_mark"),
]
