from django.urls import path

from .device_api import AttendanceDeviceConfiguration, AttendanceDeviceEvents, AttendanceDeviceHeartbeat

urlpatterns = [
    path("events/", AttendanceDeviceEvents.as_view(), name="api_attendance_device_events"),
    path("heartbeat/", AttendanceDeviceHeartbeat.as_view(), name="api_attendance_device_heartbeat"),
    path("configuration/", AttendanceDeviceConfiguration.as_view(), name="api_attendance_device_configuration"),
]
