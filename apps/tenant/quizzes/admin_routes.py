from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.admin_quiz_analytics, name="admin_quiz_analytics"),
]
