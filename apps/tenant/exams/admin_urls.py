from django.urls import path

from . import admin_views, external_views, review_views

urlpatterns = [
    # External examinations (Phase 6)
    path("external/", external_views.external_exam_dashboard, name="admin_external_exam_dashboard"),
    path("external/boards/create/", external_views.board_create, name="admin_external_exam_board_create"),
    path("external/boards/<int:pk>/edit/", external_views.board_edit, name="admin_external_exam_board_edit"),
    path("external/centres/create/", external_views.centre_create, name="admin_external_exam_centre_create"),
    path("external/centres/<int:pk>/edit/", external_views.centre_edit, name="admin_external_exam_centre_edit"),
    path("external/sessions/create/", external_views.session_create, name="admin_external_exam_session_create"),
    path("external/sessions/<int:pk>/", external_views.session_detail, name="admin_external_exam_session_detail"),
    path("external/sessions/<int:pk>/edit/", external_views.session_edit, name="admin_external_exam_session_edit"),
    path("external/sessions/<int:session_pk>/subjects/create/", external_views.subject_create, name="admin_external_exam_subject_create"),
    path("external/subjects/<int:pk>/edit/", external_views.subject_edit, name="admin_external_exam_subject_edit"),
    path("external/sessions/<int:pk>/candidates/", external_views.session_candidates, name="admin_external_exam_candidates"),
    path("external/sessions/<int:session_pk>/candidates/create/", external_views.candidate_create, name="admin_external_exam_candidate_create"),
    path("external/candidates/<int:pk>/", external_views.candidate_detail, name="admin_external_exam_candidate_detail"),
    path("external/candidates/<int:pk>/edit/", external_views.candidate_edit, name="admin_external_exam_candidate_edit"),
    path("external/candidates/<int:candidate_pk>/subjects/create/", external_views.candidate_subject_add, name="admin_external_exam_candidate_subject_add"),
    path("external/candidate-subjects/<int:pk>/edit/", external_views.candidate_subject_edit, name="admin_external_exam_candidate_subject_edit"),
    path("external/sessions/<int:pk>/export/", external_views.export_candidates, name="admin_external_exam_export_candidates"),
    path("external/sessions/<int:pk>/results/import/", external_views.import_results, name="admin_external_exam_import_results"),

    # Exams
    path("", admin_views.exam_list, name="admin_exams_list"),
    path("create/", admin_views.exam_create, name="admin_exams_create"),
    path("<int:pk>/edit/", admin_views.exam_edit, name="admin_exams_edit"),

    # Exam review console
    path("review/", review_views.review_dashboard, name="admin_exam_review_dashboard"),
    path("review/export/", review_views.export_review_csv, name="admin_exam_review_export"),
    path("review/attempts/<int:pk>/", review_views.attempt_review, name="admin_exam_review_attempt"),
    path("review/events/<int:pk>/", review_views.event_detail, name="admin_exam_review_event"),
    path("review/events/<int:pk>/resolve/", review_views.resolve_event, name="admin_exam_review_event_resolve"),

    # Exam Papers
    path("papers/", admin_views.paper_list, name="admin_exam_papers_list"),
    path("papers/create/", admin_views.paper_create, name="admin_exam_papers_create"),
    path("papers/<int:pk>/", admin_views.paper_detail, name="admin_exam_paper_detail"),
    path("papers/<int:pk>/edit/", admin_views.paper_edit, name="admin_exam_papers_edit"),
    path("papers/<int:pk>/scores/", admin_views.paper_scores, name="admin_paper_scores"),
    path("papers/<int:pk>/analytics/", admin_views.paper_analytics, name="admin_paper_analytics"),
    path("papers/<int:pk>/calculate-ranks/", admin_views.calculate_ranks, name="admin_paper_calculate_ranks"),
    path("papers/<int:pk>/assign-grades/", admin_views.assign_paper_grades, name="admin_paper_assign_grades"),

    # Paper Questions
    path("papers/<int:pk>/questions/", admin_views.paper_questions, name="admin_paper_questions"),
    path("papers/<int:pk>/add-question/", admin_views.paper_add_question, name="admin_paper_add_question"),

    # Question Bank
    path("questions/", admin_views.question_bank_list, name="admin_question_bank_list"),
    path("questions/create/", admin_views.question_bank_create, name="admin_question_bank_create"),
    path("questions/<int:pk>/edit/", admin_views.question_bank_edit, name="admin_question_bank_edit"),

    # Exam Schedules
    path("schedules/", admin_views.schedule_list, name="admin_exam_schedules_list"),
    path("schedules/create/", admin_views.schedule_create, name="admin_exam_schedule_create"),
    path("schedules/<int:pk>/", admin_views.schedule_detail, name="admin_schedule_detail"),
    path("schedules/<int:pk>/edit/", admin_views.schedule_edit, name="admin_exam_schedule_edit"),
    path("schedules/<int:pk>/allocate-seats/", admin_views.allocate_seats, name="admin_allocate_seats"),

    # Seat Allocations & Admit Cards
    path("seat-allocations/<int:pk>/admit-card/", admin_views.generate_admit_card, name="admin_generate_admit_card"),

    # Online Exam Attempts
    path("online-attempts/", admin_views.online_attempts_list, name="admin_online_attempts_list"),
]
