from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.exam_dashboard, name="student_exams_dashboard"),
    path("results/", student_views.results, name="student_exam_results"),
    path("schedules/", student_views.my_schedules, name="student_exam_schedules"),
    path("papers/<int:pk>/start/", student_views.start_exam, name="student_exam_start"),
    path("papers/<int:pk>/take/", student_views.take_exam, name="student_take_exam"),
    path("attempts/<int:pk>/event/", student_views.exam_security_event, name="student_exam_security_event"),
    path("attempts/<int:pk>/result/", student_views.exam_result, name="student_exam_result"),
    path("report-card/<int:exam_id>/pdf/", student_views.exam_report_card_pdf, name="student_exam_report_card_pdf"),
]
