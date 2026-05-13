from django.urls import path

from . import teacher_views

urlpatterns = [
    path("submissions/<int:pk>/", teacher_views.grievance_detail, name="teacher_grievances_detail"),
    path("submissions/", teacher_views.grievance_list, name="teacher_grievances_list"),
    path("", teacher_views.grievance_submit, name="teacher_grievances_submit"),
]
