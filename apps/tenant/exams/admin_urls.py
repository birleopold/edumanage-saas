from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.exam_list, name="admin_exams_list"),
    path("create/", admin_views.exam_create, name="admin_exams_create"),
    path("<int:pk>/edit/", admin_views.exam_edit, name="admin_exams_edit"),

    path("papers/", admin_views.paper_list, name="admin_exam_papers_list"),
    path("papers/create/", admin_views.paper_create, name="admin_exam_papers_create"),
    path("papers/<int:pk>/edit/", admin_views.paper_edit, name="admin_exam_papers_edit"),
    path("papers/<int:pk>/scores/", admin_views.paper_scores, name="admin_exam_paper_scores"),
]
