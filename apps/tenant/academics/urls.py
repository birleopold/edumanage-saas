from django.urls import include, path

from . import promotion_views, setup_views, views

urlpatterns = [
    path("", setup_views.academics_setup, name="admin_academics_setup"),
    path("framework/", include("apps.tenant.education_frameworks.urls")),
    path("context/", views.academic_context, name="admin_academic_context"),

    path("years/", views.year_list, name="admin_academic_year_list"),
    path("years/create/", views.year_create, name="admin_academic_year_create"),
    path("years/<int:pk>/edit/", views.year_edit, name="admin_academic_year_edit"),

    path("terms/", views.term_list, name="admin_academic_term_list"),
    path("terms/create/", views.term_create, name="admin_academic_term_create"),
    path("terms/<int:pk>/edit/", views.term_edit, name="admin_academic_term_edit"),

    path("levels/", views.level_list, name="admin_level_list"),
    path("levels/create/", views.level_create, name="admin_level_create"),
    path("levels/<int:pk>/edit/", views.level_edit, name="admin_level_edit"),

    path("programs/", views.program_list, name="admin_program_list"),
    path("programs/create/", views.program_create, name="admin_program_create"),
    path("programs/<int:pk>/edit/", views.program_edit, name="admin_program_edit"),

    path("class-groups/", views.classgroup_list, name="admin_classgroup_list"),
    path("class-groups/create/", views.classgroup_create, name="admin_classgroup_create"),
    path("class-groups/<int:pk>/edit/", views.classgroup_edit, name="admin_classgroup_edit"),

    path("courses/", views.course_list, name="admin_course_list"),
    path("courses/create/", views.course_create, name="admin_course_create"),
    path("courses/<int:pk>/edit/", views.course_edit, name="admin_course_edit"),

    path("offerings/", views.offering_list, name="admin_offering_list"),
    path("offerings/create/", views.offering_create, name="admin_offering_create"),
    path("offerings/<int:pk>/edit/", views.offering_edit, name="admin_offering_edit"),

    path("enrollments/", views.enrollment_list, name="admin_enrollment_list"),
    path("enrollments/bulk/", views.enrollment_bulk, name="admin_enrollment_bulk"),
    path(
        "enrollments/bulk-status/",
        views.enrollment_bulk_status,
        name="admin_enrollment_bulk_status",
    ),
    path("enrollments/create/", views.enrollment_create, name="admin_enrollment_create"),
    path("enrollments/<int:pk>/edit/", views.enrollment_edit, name="admin_enrollment_edit"),

    path("grading-scales/", views.grading_scale_list, name="admin_grading_scale_list"),
    path("grading-scales/create/", views.grading_scale_create, name="admin_grading_scale_create"),
    path("grading-scales/<int:pk>/", views.grading_scale_detail, name="admin_grading_scale_detail"),
    path("grading-scales/<int:pk>/edit/", views.grading_scale_edit, name="admin_grading_scale_edit"),
    path("grading-scales/<int:scale_id>/ranges/create/", views.grade_range_create, name="admin_grade_range_create"),
    path("grade-ranges/<int:pk>/edit/", views.grade_range_edit, name="admin_grade_range_edit"),

    path("streams/", views.stream_list, name="admin_stream_list"),
    path("streams/create/", views.stream_create, name="admin_stream_create"),
    path("streams/<int:pk>/edit/", views.stream_edit, name="admin_stream_edit"),
    path(
        "promotions/stream/",
        promotion_views.stream_promotion,
        name="admin_stream_promotion",
    ),

    path("report-cards/<int:student_id>/<int:term_id>/", views.report_card_view, name="admin_report_card_view"),
    path("terms/<int:term_id>/report-cards/<int:student_id>/", views.report_card_view, name="admin_report_card"),
    path("terms/<int:term_id>/report-cards/", views.term_report_cards, name="admin_term_report_cards"),
]
