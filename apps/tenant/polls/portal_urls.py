from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.poll_list, name="poll_list"),
    path("<int:pk>/", portal_views.poll_detail, name="poll_detail"),
    path("<int:pk>/vote/", portal_views.poll_vote, name="poll_vote"),
    path("<int:pk>/results/", portal_views.poll_results, name="poll_results"),
]
