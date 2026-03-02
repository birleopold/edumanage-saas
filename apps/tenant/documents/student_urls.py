from django.urls import path

from . import student_views

urlpatterns = [
    path("", student_views.document_list, name="student_documents_list"),
    path("<int:pk>/download/", student_views.document_download, name="student_documents_download"),
]
