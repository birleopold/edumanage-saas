from django.urls import path

from . import views

urlpatterns = [
    path("", views.teacher_list, name="admin_teachers_list"),
    path("create/", views.teacher_create, name="admin_teachers_create"),
    path("<int:pk>/credentials/", views.teacher_credentials, name="admin_teachers_credentials"),
    path("<int:pk>/edit/", views.teacher_edit, name="admin_teachers_edit"),
]
