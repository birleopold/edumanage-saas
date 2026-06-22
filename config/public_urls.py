from django.urls import include, path

from apps.public.tenants import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("platform/", include("apps.public.tenants.platform_urls")),
]
