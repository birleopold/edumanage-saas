from django.urls import path
from . import admin_views

urlpatterns = [
    path("delivery/", admin_views.delivery_dashboard, name="msg_delivery"),
    path("copy/", admin_views.template_list, name="msg_copy"),
    path("copy/new/", admin_views.template_edit, name="msg_copy_new"),
    path("copy/<int:pk>/", admin_views.template_edit, name="msg_copy_edit"),
]
