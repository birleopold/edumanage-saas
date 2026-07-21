from django.urls import path

from . import activity_views, admin_views, dashboard_views

urlpatterns = [
    path("", dashboard_views.coursework_dashboard, name="admin_coursework_dashboard"),
    path("activities/", activity_views.activity_framework_dashboard, name="admin_coursework_activity_framework"),
    path("activities/<int:pk>/edit/", activity_views.activity_policy_edit, name="admin_coursework_activity_policy_edit"),
    path("materials/", admin_views.material_list, name="admin_coursework_materials_list"),
    path("materials/create/", admin_views.material_create, name="admin_coursework_materials_create"),
    path("materials/<int:pk>/edit/", admin_views.material_edit, name="admin_coursework_materials_edit"),
    path(
        "materials/<int:pk>/attachments/add/",
        admin_views.material_attachment_add,
        name="admin_coursework_materials_attachments_add",
    ),
    path(
        "materials/<int:pk>/attachments/<int:attachment_id>/remove/",
        admin_views.material_attachment_remove,
        name="admin_coursework_materials_attachments_remove",
    ),

    path("assignments/", admin_views.assignment_list, name="admin_coursework_assignments_list"),
    path("assignments/create/", admin_views.assignment_create, name="admin_coursework_assignments_create"),
    path("assignments/<int:pk>/edit/", admin_views.assignment_edit, name="admin_coursework_assignments_edit"),
    path(
        "assignments/<int:pk>/attachments/add/",
        admin_views.assignment_attachment_add,
        name="admin_coursework_assignments_attachments_add",
    ),
    path(
        "assignments/<int:pk>/attachments/<int:attachment_id>/remove/",
        admin_views.assignment_attachment_remove,
        name="admin_coursework_assignments_attachments_remove",
    ),
]
