from django.urls import path

from . import teacher_views

urlpatterns = [
    path("", teacher_views.document_list, name="teacher_documents_list"),
    path("<int:pk>/download/", teacher_views.document_download, name="teacher_documents_download"),
]
