from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.document_list, name="admin_documents_list"),
    path("upload/", admin_views.document_upload, name="admin_documents_upload"),
    path("<int:pk>/edit/", admin_views.document_edit, name="admin_documents_edit"),
    path("<int:pk>/download/", admin_views.document_download, name="admin_documents_download"),
]
