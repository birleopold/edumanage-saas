from django.urls import path

from . import admin_views, welfare_views

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

    path("welfare/", welfare_views.welfare_dashboard, name="admin_boarding_welfare_dashboard"),
    path("welfare/profiles/", welfare_views.boarding_profile_list, name="admin_boarding_profiles"),
    path("welfare/profiles/create/", welfare_views.boarding_profile_create, name="admin_boarding_profile_create"),
    path("welfare/profiles/<int:pk>/edit/", welfare_views.boarding_profile_edit, name="admin_boarding_profile_edit"),
    path("welfare/students/<int:student_pk>/", welfare_views.student_welfare_detail, name="admin_boarding_student_timeline"),

    path("welfare/leaves/", welfare_views.boarding_leave_list, name="admin_boarding_leaves"),
    path("welfare/leaves/create/", welfare_views.boarding_leave_create, name="admin_boarding_leave_create"),
    path("welfare/leaves/<int:pk>/", welfare_views.boarding_leave_detail, name="admin_boarding_leave_detail"),
    path("welfare/leaves/<int:pk>/<str:action>/", welfare_views.boarding_leave_transition, name="admin_boarding_leave_transition"),

    path("welfare/roll-calls/", welfare_views.hostel_roll_call_list, name="admin_hostel_roll_calls"),
    path("welfare/roll-calls/create/", welfare_views.hostel_roll_call_create, name="admin_hostel_roll_call_create"),
    path("welfare/roll-calls/<int:pk>/", welfare_views.hostel_roll_call_detail, name="admin_hostel_roll_call_detail"),
    path("welfare/roll-calls/<int:pk>/populate/", welfare_views.hostel_roll_call_populate, name="admin_hostel_roll_call_populate"),

    path("welfare/cases/", welfare_views.welfare_case_list, name="admin_welfare_cases"),
    path("welfare/cases/create/", welfare_views.welfare_case_create, name="admin_welfare_case_create"),
    path("welfare/cases/<int:pk>/", welfare_views.welfare_case_detail, name="admin_welfare_case_detail"),
    path("welfare/cases/<int:pk>/edit/", welfare_views.welfare_case_edit, name="admin_welfare_case_edit"),
]
