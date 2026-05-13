from django.urls import path

from . import parent_portal_views

urlpatterns = [
    path(
        "<int:student_pk>/id-card/",
        parent_portal_views.parent_child_id_card_pdf,
        name="parent_child_id_card_pdf",
    ),
]
