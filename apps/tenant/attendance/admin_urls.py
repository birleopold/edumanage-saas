from django.urls import path

from . import admin_views

urlpatterns = [
    path("sessions/", admin_views.session_list, name="admin_attendance_sessions_list"),
    path(
        "sessions/<int:pk>/",
        admin_views.session_detail,
        name="admin_attendance_session_detail",
    ),
]
