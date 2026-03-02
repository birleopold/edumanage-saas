from django.urls import path

from . import admin_views

urlpatterns = [
    path("vehicles/", admin_views.vehicle_list, name="admin_transport_vehicles_list"),
    path("vehicles/create/", admin_views.vehicle_create, name="admin_transport_vehicles_create"),
    path("vehicles/<int:pk>/edit/", admin_views.vehicle_edit, name="admin_transport_vehicles_edit"),

    path("routes/", admin_views.route_list, name="admin_transport_routes_list"),
    path("routes/create/", admin_views.route_create, name="admin_transport_routes_create"),
    path("routes/<int:pk>/edit/", admin_views.route_edit, name="admin_transport_routes_edit"),

    path("stops/", admin_views.stop_list, name="admin_transport_stops_list"),
    path("stops/create/", admin_views.stop_create, name="admin_transport_stops_create"),
    path("stops/<int:pk>/edit/", admin_views.stop_edit, name="admin_transport_stops_edit"),

    path("assignments/", admin_views.assignment_list, name="admin_transport_assignments_list"),
    path("assignments/create/", admin_views.assignment_create, name="admin_transport_assignments_create"),
    path("assignments/<int:pk>/edit/", admin_views.assignment_edit, name="admin_transport_assignments_edit"),
]
