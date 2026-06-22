from django.urls import path

from . import notification_views

urlpatterns = [
    path("", notification_views.notification_list, name="notifications_list"),
    path("compose/", notification_views.notification_compose, name="notifications_compose"),
    path("mark-all-read/", notification_views.notification_mark_all_read, name="notifications_mark_all_read"),
    path("<int:pk>/read/", notification_views.notification_read, name="notifications_read"),
]
