from django.urls import path

from . import parent_views

urlpatterns = [
    path("", parent_views.document_list, name="parent_documents_list"),
    path("<int:pk>/download/", parent_views.document_download, name="parent_documents_download"),
]
