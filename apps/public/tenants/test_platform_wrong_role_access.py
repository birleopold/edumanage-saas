from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.tenant.users.models import User

from .platform_auth_views import platform_access_denied, platform_login
from .platform_views import platform_admin_required


@override_settings(
    ROOT_URLCONF="config.public_urls",
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
)
class PlatformWrongRoleAccessTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User(username="school-admin", is_superuser=False, is_staff=True)

    def _request(self, path):
        request = self.factory.get(path)
        SessionMiddleware(lambda current_request: HttpResponse()).process_request(request)
        request.session.save()
        MessageMiddleware(lambda current_request: HttpResponse()).process_request(request)
        request.user = self.user
        return request

    def test_platform_guard_has_public_schema_fallback_for_wrong_role(self):
        request = self._request(reverse("platform_dashboard"))
        protected_view = platform_admin_required(lambda current_request: HttpResponse("ok"))

        response = protected_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("landing_page"))
        self.assertEqual(reverse("landing_page"), "/platform/access-denied/")

    def test_access_denied_clears_wrong_role_session_and_returns_to_login(self):
        request = self._request(reverse("landing_page"))
        request.session["_auth_user_id"] = "123"

        response = platform_access_denied(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{reverse('platform_admin_login')}?next="))
        self.assertFalse(request.user.is_authenticated)
        self.assertNotIn("_auth_user_id", request.session)
        self.assertEqual(
            [str(message) for message in get_messages(request)],
            ["Only platform superusers can access the SaaS management console."],
        )

    def test_platform_login_clears_authenticated_non_superuser(self):
        request = self._request(reverse("platform_admin_login"))
        request.session["_auth_user_id"] = "123"

        response = platform_login(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{reverse('platform_admin_login')}?next="))
        self.assertFalse(request.user.is_authenticated)
        self.assertNotIn("_auth_user_id", request.session)
