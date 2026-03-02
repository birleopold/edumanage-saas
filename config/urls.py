from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.tenant.portals import error_handlers

urlpatterns = [
    path("dj-admin/", admin.site.urls),
    path("", include("apps.tenant.portals.urls")),
    path("api/v1/", include("apps.tenant.portals.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler404 = error_handlers.handler404
handler500 = error_handlers.handler500
handler403 = error_handlers.handler403
