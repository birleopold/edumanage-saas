from django.urls import path

from . import admin_views, device_admin_views, device_setup_views, workspace_views

urlpatterns = [
    path("", workspace_views.attendance_dashboard, name="admin_attendance_device_dashboard"),
    path("sessions/", admin_views.session_list, name="admin_attendance_sessions_list"),
    path(
        "sessions/<int:pk>/",
        admin_views.session_detail,
        name="admin_attendance_session_detail",
    ),
    path("staff/", workspace_views.staff_attendance, name="admin_attendance_staff"),
    path("staff/manual/", workspace_views.staff_attendance_manual, name="admin_attendance_staff_manual"),
    path("devices/", device_admin_views.device_list, name="admin_attendance_device_list"),
    path("devices/add/", device_admin_views.device_create, name="admin_attendance_device_create"),
    path("devices/<int:pk>/setup/", device_setup_views.device_setup, name="admin_attendance_device_setup"),
    path(
        "devices/<int:pk>/setup/status.json",
        device_setup_views.device_setup_status,
        name="admin_attendance_device_setup_status",
    ),
    path(
        "devices/<int:pk>/setup/edge-config.json",
        device_setup_views.download_edge_config,
        name="admin_attendance_device_edge_config",
    ),
    path("devices/<int:pk>/", device_admin_views.device_detail, name="admin_attendance_device_detail"),
    path("devices/<int:pk>/edit/", device_admin_views.device_edit, name="admin_attendance_device_edit"),
    path("events/", device_admin_views.event_list, name="admin_attendance_device_event_list"),
    path("daily/", device_admin_views.daily_list, name="admin_attendance_daily_list"),
    path("daily/<int:pk>/adjust/", device_admin_views.daily_adjust, name="admin_attendance_daily_adjust"),
    path("policies/", device_admin_views.policy_list, name="admin_attendance_policy_list"),
    path("policies/add/", device_admin_views.policy_create, name="admin_attendance_policy_create"),
    path("policies/<int:pk>/edit/", device_admin_views.policy_edit, name="admin_attendance_policy_edit"),
    path("import/", device_admin_views.csv_import, name="admin_attendance_csv_import"),
    path("staff-timesheet.csv", device_admin_views.timesheet_csv, name="admin_attendance_staff_timesheet_csv"),
    path("integration-guide/", device_admin_views.integration_guide, name="admin_attendance_integration_guide"),
]
