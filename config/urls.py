from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.tenant.finance import login_links
from apps.tenant.portals import error_handlers
from apps.tenant.users import device_portal

urlpatterns = [
    path("dj-admin/", admin.site.urls),
    path("messages/", include("apps.tenant.messaging.urls")),
    path("message-ops/", include("apps.tenant.messaging.ops")),
    path("analytics-portal/", include("apps.tenant.analytics.portal_urls")),
    path("polls/", include("apps.tenant.polls.portal_urls")),
    path("admin/polls/", include("apps.tenant.polls.manage_urls")),
    path("teacher/polls/", include("apps.tenant.polls.portal_urls")),
    path("student/polls/", include("apps.tenant.polls.portal_urls")),
    path("parent/polls/", include("apps.tenant.polls.portal_urls")),
    path("external-login/<str:provider_type>/", login_links.external_login_start, name="external_login_start"),
    path("external-login/callback/", login_links.external_login_callback, name="external_login_callback"),
    path("profile/devices/", device_portal.my_devices, name="my_devices"),
    path("profile/devices/<int:pk>/disable/", device_portal.deactivate_my_device, name="my_device_deactivate"),
    path("", include("apps.tenant.portals.urls")),
    path("api/v1/", include("apps.tenant.portals.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler404 = error_handlers.handler404
handler500 = error_handlers.handler500
handler403 = error_handlers.handler403
