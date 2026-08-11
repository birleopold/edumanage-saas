from django.urls import include, path

from . import campus_scoped_views, pathway_views, promotion_scope, setup_views, views

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

    path("pathways/", pathway_views.pathway_dashboard, name="admin_pathway_dashboard"),
    path("pathways/create/", pathway_views.pathway_create, name="admin_pathway_create"),
    path("pathways/offerings/", pathway_views.pathway_offerings, name="admin_pathway_offerings"),
    path("pathways/assignments/create/", pathway_views.pathway_assignment_create, name="admin_pathway_assignment_create"),
    path("pathways/assignments/<int:pk>/edit/", pathway_views.pathway_assignment_edit, name="admin_pathway_assignment_edit"),
    path("pathways/<int:pk>/", pathway_views.pathway_detail, name="admin_pathway_detail"),
    path("pathways/<int:pk>/edit/", pathway_views.pathway_edit, name="admin_pathway_edit"),
    path("pathways/<int:pathway_pk>/levels/create/", pathway_views.pathway_level_create, name="admin_pathway_level_create"),
    path("pathway-levels/<int:pk>/edit/", pathway_views.pathway_level_edit, name="admin_pathway_level_edit"),
    path("pathways/<int:pathway_pk>/combinations/create/", pathway_views.combination_create, name="admin_combination_create"),
    path("combinations/<int:pk>/", pathway_views.combination_detail, name="admin_combination_detail"),
    path("combinations/<int:pk>/edit/", pathway_views.combination_edit, name="admin_combination_edit"),
    path("combinations/<int:combination_pk>/courses/create/", pathway_views.combination_course_create, name="admin_combination_course_create"),
    path("combination-courses/<int:pk>/edit/", pathway_views.combination_course_edit, name="admin_combination_course_edit"),

    path("class-groups/", campus_scoped_views.classgroup_list, name="admin_classgroup_list"),
    path("class-groups/create/", campus_scoped_views.classgroup_create, name="admin_classgroup_create"),
    path("class-groups/<int:pk>/edit/", campus_scoped_views.classgroup_edit, name="admin_classgroup_edit"),

    path("courses/", views.course_list, name="admin_course_list"),
    path("courses/create/", views.course_create, name="admin_course_create"),
    path("courses/<int:pk>/edit/", views.course_edit, name="admin_course_edit"),

    path("offerings/", campus_scoped_views.offering_list, name="admin_offering_list"),
    path("offerings/create/", campus_scoped_views.offering_create, name="admin_offering_create"),
    path("offerings/<int:pk>/edit/", campus_scoped_views.offering_edit, name="admin_offering_edit"),

    path("enrollments/", campus_scoped_views.enrollment_list, name="admin_enrollment_list"),
    path("enrollments/bulk/", campus_scoped_views.enrollment_bulk, name="admin_enrollment_bulk"),
    path(
        "enrollments/bulk-status/",
        campus_scoped_views.enrollment_bulk_status,
        name="admin_enrollment_bulk_status",
    ),
    path("enrollments/create/", campus_scoped_views.enrollment_create, name="admin_enrollment_create"),
    path("enrollments/<int:pk>/edit/", campus_scoped_views.enrollment_edit, name="admin_enrollment_edit"),

    path("grading-scales/", views.grading_scale_list, name="admin_grading_scale_list"),
    path("grading-scales/create/", views.grading_scale_create, name="admin_grading_scale_create"),
    path("grading-scales/<int:pk>/", views.grading_scale_detail, name="admin_grading_scale_detail"),
    path("grading-scales/<int:pk>/edit/", views.grading_scale_edit, name="admin_grading_scale_edit"),
    path("grading-scales/<int:scale_id>/ranges/create/", views.grade_range_create, name="admin_grade_range_create"),
    path("grade-ranges/<int:pk>/edit/", views.grade_range_edit, name="admin_grade_range_edit"),

    path("streams/", campus_scoped_views.stream_list, name="admin_stream_list"),
    path("streams/create/", campus_scoped_views.stream_create, name="admin_stream_create"),
    path("streams/<int:pk>/edit/", campus_scoped_views.stream_edit, name="admin_stream_edit"),
    path(
        "promotions/stream/",
        promotion_scope.stream_promotion,
        name="admin_stream_promotion",
    ),

    path("report-cards/<int:student_id>/<int:term_id>/", campus_scoped_views.report_card_view, name="admin_report_card_view"),
    path("terms/<int:term_id>/report-cards/<int:student_id>/", campus_scoped_views.report_card_view, name="admin_report_card"),
    path("terms/<int:term_id>/report-cards/", campus_scoped_views.term_report_cards, name="admin_term_report_cards"),
]
