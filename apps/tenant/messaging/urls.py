from django.urls import path

from . import views

urlpatterns = [
    path("", views.inbox, name="messaging_inbox"),
    path("outbox/", views.outbox, name="messaging_outbox"),
    path("new/", views.conversation_new, name="messaging_conversation_new"),
    path("parent-teacher/", views.parent_teacher_chat, name="messaging_parent_teacher_chat"),
    path("bulk/", views.bulk_message, name="messaging_bulk_message"),
    path("<int:pk>/", views.conversation_detail, name="messaging_conversation_detail"),
]
