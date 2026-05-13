from django.urls import path

from . import self_service_views

urlpatterns = [
    path("", self_service_views.student_id_card_self, name="student_id_card_self"),
]
