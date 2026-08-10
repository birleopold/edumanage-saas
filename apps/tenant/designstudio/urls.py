from django.urls import path

from . import views

app_name = "designstudio"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("templates/new/", views.template_form, name="template_create"),
    path("templates/<int:pk>/edit/", views.template_form, name="template_edit"),
    path("templates/<int:pk>/duplicate/", views.template_duplicate, name="template_duplicate"),
    path("templates/<int:pk>/designer/", views.editor, name="editor"),
    path("templates/<int:pk>/preview/", views.preview_pdf, name="preview_pdf"),
    path("templates/<int:pk>/generate/", views.generate_document, name="generate"),
    path("versions/<int:pk>/<str:action>/", views.version_action, name="version_action"),
    path("issued/<int:pk>/download/", views.issued_download, name="issued_download"),
    path("issued/<int:pk>/revoke/", views.issued_revoke, name="issued_revoke"),
    path("verify/<str:token>/", views.verify_document, name="verify"),
]
