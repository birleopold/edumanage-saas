from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.coursework_home, name="student_coursework_home"),
    path("materials/<int:pk>/", student_views.material_detail, name="student_coursework_material_detail"),
    path("materials/<int:pk>/complete/", student_views.material_complete, name="student_coursework_material_complete"),
    path("assignments/<int:pk>/", student_views.assignment_detail, name="student_coursework_assignment_detail"),
    path("assignments/<int:pk>/submit/", student_views.assignment_submit, name="student_coursework_assignment_submit"),
    path("assignments/<int:pk>/submitted/", student_views.assignment_submitted, name="student_coursework_assignment_submitted"),
]
