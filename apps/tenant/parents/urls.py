from django.urls import path

from . import views

urlpatterns = [
    path("", views.parent_list, name="admin_parents_list"),
    path("create/", views.parent_create, name="admin_parents_create"),
    path("<int:pk>/credentials/", views.parent_credentials, name="admin_parents_credentials"),
    path("<int:pk>/edit/", views.parent_edit, name="admin_parents_edit"),
    path("<int:pk>/students/add/", views.parent_add_student, name="admin_parents_add_student"),
    path(
        "<int:pk>/students/<int:link_id>/remove/",
        views.parent_remove_student,
        name="admin_parents_remove_student",
    ),
]
