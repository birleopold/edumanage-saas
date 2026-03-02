from django.urls import path

from . import admin_views

urlpatterns = [
    path("hostels/", admin_views.hostel_list, name="admin_hostels_list"),
    path("hostels/create/", admin_views.hostel_create, name="admin_hostels_create"),
    path("hostels/<int:pk>/edit/", admin_views.hostel_edit, name="admin_hostels_edit"),

    path("rooms/", admin_views.room_list, name="admin_hostel_rooms_list"),
    path("rooms/create/", admin_views.room_create, name="admin_hostel_rooms_create"),
    path("rooms/<int:pk>/edit/", admin_views.room_edit, name="admin_hostel_rooms_edit"),

    path("beds/", admin_views.bed_list, name="admin_hostel_beds_list"),
    path("beds/create/", admin_views.bed_create, name="admin_hostel_beds_create"),
    path("beds/<int:pk>/edit/", admin_views.bed_edit, name="admin_hostel_beds_edit"),

    path("allocations/", admin_views.allocation_list, name="admin_bed_allocations_list"),
    path("allocations/create/", admin_views.allocation_create, name="admin_bed_allocations_create"),
    path("allocations/<int:pk>/edit/", admin_views.allocation_edit, name="admin_bed_allocations_edit"),
]
