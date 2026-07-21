from django.urls import path

from . import relationship_views, views

urlpatterns = [
    path("", views.parent_list, name="admin_parents_list"),
    path("create/", relationship_views.parent_create, name="admin_parents_create"),
    path("digests/send-all/", views.parent_digest_send_all, name="admin_parents_digest_send_all"),
    path("<int:pk>/credentials/", views.parent_credentials, name="admin_parents_credentials"),
    path("<int:pk>/digest/", views.parent_digest_preview, name="admin_parents_digest"),
    path("<int:pk>/digest/send/", views.parent_digest_send, name="admin_parents_digest_send"),
    path("<int:pk>/edit/", views.parent_edit, name="admin_parents_edit"),
    path(
        "<int:pk>/students/add/",
        relationship_views.parent_add_student,
        name="admin_parents_add_student",
    ),
    path(
        "<int:pk>/students/<int:link_id>/remove/",
        views.parent_remove_student,
        name="admin_parents_remove_student",
    ),
]
