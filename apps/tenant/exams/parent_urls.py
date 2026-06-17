from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.results, name="parent_exam_results"),
    path("student/<int:student_id>/attempt/<int:attempt_id>/", parent_views.exam_attempt_detail, name="parent_exam_attempt_detail"),
    path("student/<int:student_id>/report-card/<int:exam_id>/pdf/", parent_views.exam_report_card_pdf, name="parent_exam_report_card_pdf"),
]
