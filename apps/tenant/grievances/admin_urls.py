from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.grievance_list, name="admin_grievances_list"),
    path("<int:pk>/", admin_views.grievance_detail, name="admin_grievances_detail"),
]
