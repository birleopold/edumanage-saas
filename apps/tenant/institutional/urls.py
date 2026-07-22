from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="institutional_dashboard"),
    path("my-records/", views.my_records, name="institutional_my_records"),
    path("my-records/<int:student_id>/", views.my_records, name="institutional_student_records"),
    path("teacher/observations/", views.teacher_observations, name="institutional_teacher_observations"),
    path("teacher/observations/<int:student_id>/", views.teacher_observations, name="institutional_teacher_student_observations"),
    path("documents/permit/<int:pk>.pdf", views.permit_download, name="institutional_permit_pdf"),
    path("documents/transcript/<int:student_id>.pdf", views.transcript_download, name="institutional_transcript_pdf"),
    path("documents/report/<int:student_id>.pdf", views.report_download, name="institutional_report_pdf"),
    path("verify/<str:token>/", views.verify_document, name="institutional_verify"),
    path("permits/<int:pk>/revoke/", views.revoke_permit, name="institutional_permit_revoke"),
    path("<slug:resource>/new/", views.resource_form, name="institutional_resource_create"),
    path("<slug:resource>/<int:pk>/edit/", views.resource_form, name="institutional_resource_edit"),
    path("<slug:resource>/", views.resource_list, name="institutional_resource_list"),
]
