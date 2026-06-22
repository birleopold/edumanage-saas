from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.admin_poll_list, name="admin_poll_list"),
    path("create/", portal_views.admin_poll_create, name="admin_poll_create"),
    path("<int:pk>/", portal_views.admin_poll_detail, name="admin_poll_detail"),
    path("<int:pk>/edit/", portal_views.admin_poll_edit, name="admin_poll_edit"),
    path("<int:pk>/toggle/", portal_views.admin_poll_toggle, name="admin_poll_toggle"),
    path("<int:pk>/options/add/", portal_views.admin_poll_option_add, name="admin_poll_option_add"),
]
