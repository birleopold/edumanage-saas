from django.urls import path

from . import views, bulk_views

urlpatterns = [
    path("", views.student_list, name="admin_students_list"),
    path("create/", views.student_create, name="admin_students_create"),
    path("export/csv/", views.student_export_csv, name="admin_students_export_csv"),
    path("<int:pk>/id-card/", views.student_id_card_pdf, name="admin_students_id_card_pdf"),
    path("<int:pk>/credentials/", views.student_credentials, name="admin_students_credentials"),
    path("<int:pk>/", views.student_edit, name="admin_students_detail"),
    path("<int:pk>/edit/", views.student_edit, name="admin_students_edit"),
    path("bulk-import/", bulk_views.bulk_import_students, name="admin_students_bulk_import"),
    path("bulk-import/results/", bulk_views.bulk_import_results, name="admin_students_bulk_import_results"),
    path("bulk-import/download-csv/", bulk_views.download_credentials_csv, name="admin_students_download_credentials_csv"),
    path("bulk-import/template/", bulk_views.download_sample_template, name="admin_students_download_template"),
]
