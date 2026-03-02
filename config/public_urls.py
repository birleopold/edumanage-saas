from django.urls import path

from apps.public.tenants import views

urlpatterns = [
    path("health/", views.health, name="health"),
]
