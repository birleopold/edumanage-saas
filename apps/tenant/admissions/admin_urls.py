from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.applicant_list, name="admin_admissions_applicants"),
    path("create/", admin_views.applicant_create, name="admin_admissions_applicant_create"),
    path("<int:pk>/", admin_views.applicant_detail, name="admin_admissions_applicant_detail"),
    path("<int:pk>/edit/", admin_views.applicant_edit, name="admin_admissions_applicant_edit"),
    path("<int:pk>/set-status/", admin_views.applicant_set_status, name="admin_admissions_applicant_set_status"),
    path("<int:pk>/admit/", admin_views.applicant_admit, name="admin_admissions_applicant_admit"),
    path("<int:pk>/reject/", admin_views.applicant_reject, name="admin_admissions_applicant_reject"),
]
