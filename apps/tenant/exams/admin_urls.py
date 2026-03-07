from django.urls import path

from . import admin_views

urlpatterns = [
    # Exams
    path("", admin_views.exam_list, name="admin_exams_list"),
    path("create/", admin_views.exam_create, name="admin_exams_create"),
    path("<int:pk>/edit/", admin_views.exam_edit, name="admin_exams_edit"),

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
