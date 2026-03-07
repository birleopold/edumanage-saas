from django.urls import include, path

from . import admin_views

urlpatterns = [
    path("", admin_views.staff_list, name="admin_hr_staff_list"),
    path("staff/create/", admin_views.staff_create, name="admin_hr_staff_create"),
    path("staff/<int:pk>/", admin_views.staff_detail, name="admin_hr_staff_detail"),
    path("staff/<int:pk>/edit/", admin_views.staff_edit, name="admin_hr_staff_edit"),
    path("department-heads/", admin_views.department_head_list, name="admin_hr_department_heads_list"),
    path("department-heads/create/", admin_views.department_head_create, name="admin_hr_department_head_create"),
    path("department-heads/<int:pk>/edit/", admin_views.department_head_edit, name="admin_hr_department_head_edit"),
    path("departments/", admin_views.department_list, name="admin_hr_departments_list"),
    path("departments/create/", admin_views.department_create, name="admin_hr_department_create"),
    path("departments/<int:pk>/edit/", admin_views.department_edit, name="admin_hr_department_edit"),
    path("positions/", admin_views.position_list, name="admin_hr_positions_list"),
    path("positions/create/", admin_views.position_create, name="admin_hr_position_create"),
    path("positions/<int:pk>/edit/", admin_views.position_edit, name="admin_hr_position_edit"),
    path("payroll/", include("apps.tenant.hr.payroll_urls")),
]
