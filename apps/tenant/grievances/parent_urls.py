from django.urls import path

from . import parent_views

urlpatterns = [
    path("submissions/<int:pk>/", parent_views.grievance_detail, name="parent_grievances_detail"),
    path("submissions/", parent_views.grievance_list, name="parent_grievances_list"),
    path("", parent_views.grievance_submit, name="parent_grievances_submit"),
]
