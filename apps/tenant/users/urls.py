from django.urls import path

from . import device_portal, setup_views, views

urlpatterns = [
    path("", views.user_list, name="admin_users_list"),
    path("devices/test-push/", device_portal.admin_test_pwa_push, name="admin_user_devices_test_push"),
    path("devices/", device_portal.admin_device_monitor, name="admin_user_devices"),
    path("<int:pk>/roles/", views.user_roles_edit, name="admin_users_roles_edit"),
    path("setup/<str:token>/", setup_views.password_setup, name="password_setup"),
]
