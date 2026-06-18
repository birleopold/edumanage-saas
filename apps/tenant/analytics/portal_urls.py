from django.urls import path

from . import intelligence_views

urlpatterns = [
    path("teacher/", intelligence_views.teacher_dashboard, name="teacher_analytics_dashboard"),
    path("student/", intelligence_views.student_trends, name="student_analytics_trends"),
    path("parent/", intelligence_views.parent_trends, name="parent_analytics_trends"),
]
