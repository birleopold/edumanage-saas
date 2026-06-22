from django.urls import path

from . import admin_views, schedule_views

urlpatterns = [
    path("drivers/", admin_views.driver_list, name="admin_transport_drivers_list"),
    path("drivers/create/", admin_views.driver_create, name="admin_transport_driver_create"),
    path("drivers/<int:pk>/edit/", admin_views.driver_edit, name="admin_transport_driver_edit"),
    path("vehicles/", admin_views.vehicle_list, name="admin_transport_vehicles_list"),
    path("vehicles/create/", admin_views.vehicle_create, name="admin_transport_vehicle_create"),
    path("vehicles/<int:pk>/edit/", admin_views.vehicle_edit, name="admin_transport_vehicle_edit"),
    path("vehicles/<int:pk>/tracking/", admin_views.vehicle_tracking, name="admin_transport_vehicle_tracking"),
    path("routes/", admin_views.route_list, name="admin_transport_routes_list"),
    path("routes/create/", admin_views.route_create, name="admin_transport_route_create"),
    path("routes/<int:pk>/", admin_views.route_detail, name="admin_transport_route_detail"),
    path("routes/<int:pk>/edit/", admin_views.route_edit, name="admin_transport_route_edit"),
    path("schedules/", schedule_views.schedule_list, name="admin_transport_schedules_list"),
    path("schedules/create/", schedule_views.schedule_create, name="admin_transport_schedule_create"),
    path("schedules/<int:pk>/edit/", schedule_views.schedule_edit, name="admin_transport_schedule_edit"),
    path("notices/", schedule_views.notice_list, name="admin_transport_notices_list"),
    path("notices/create/", schedule_views.notice_create, name="admin_transport_notice_create"),
    path("stops/", admin_views.stop_list, name="admin_transport_stops_list"),
    path("stops/create/", admin_views.stop_create, name="admin_transport_stop_create"),
    path("stops/<int:pk>/edit/", admin_views.stop_edit, name="admin_transport_stop_edit"),
    path("assignments/", admin_views.assignment_list, name="admin_transport_assignments_list"),
    path("assignments/create/", admin_views.assignment_create, name="admin_transport_assignment_create"),
    path("assignments/<int:pk>/edit/", admin_views.assignment_edit, name="admin_transport_assignment_edit"),
]
