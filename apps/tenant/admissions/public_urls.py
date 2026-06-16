from django.urls import path

from . import public_views

urlpatterns = [
    path("", public_views.public_application_create, name="public_admissions_apply"),
    path("track/", public_views.public_application_track, name="public_admissions_track"),
    path("submitted/<str:reference>/", public_views.public_application_success, name="public_admissions_success"),
]
