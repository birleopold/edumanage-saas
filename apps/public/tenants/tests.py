from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .forms import normalize_domain
from .middleware import TenantStatusMiddleware
from .platform_views import _login_redirect_url, _safe_next_url
from .views import health


class PublicHealthViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_health_returns_monitor_friendly_json(self):
        response = health(self.factory.get("/health/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertIn(b'"status": "ok"', response.content)
        self.assertIn(b'"service": "edumanage"', response.content)


class TenantStatusMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _middleware(self):
        return TenantStatusMiddleware(lambda request: HttpResponse("ok"))

    def test_active_tenant_is_allowed(self):
        request = self.factory.get("/admin/")
        request.tenant = SimpleNamespace(schema_name="school_one", status="active", name="School One")

        response = self._middleware()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_public_schema_is_never_marked_unavailable(self):
        request = self.factory.get("/platform/")
        request.tenant = SimpleNamespace(schema_name="public", status="suspended", name="Public")

        response = self._middleware()(request)

        self.assertEqual(response.status_code, 200)

    def test_suspended_tenant_gets_unavailable_page(self):
        request = self.factory.get("/admin/")
        request.tenant = SimpleNamespace(schema_name="school_one", status="suspended", name="School One")

        response = self._middleware()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"School Portal Unavailable", response.content)

    def test_archived_tenant_gets_unavailable_page(self):
        request = self.factory.get("/student/")
        request.tenant = SimpleNamespace(schema_name="school_one", status="archived", name="School One")

        response = self._middleware()(request)

        self.assertEqual(response.status_code, 403)

    @override_settings(TENANT_STATUS_EXEMPT_PATH_PREFIXES=("/health/",))
    def test_exempt_path_stays_available(self):
        request = self.factory.get("/health/")
        request.tenant = SimpleNamespace(schema_name="school_one", status="suspended", name="School One")

        response = self._middleware()(request)

        self.assertEqual(response.status_code, 200)


class PlatformRedirectSafetyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_login_redirect_url_encodes_next_path(self):
        request = self.factory.get("/platform/tenants/?q=A&B=1")
        request.user = AnonymousUser()

        login_url = _login_redirect_url(request)

        self.assertTrue(login_url.startswith("/platform/login/?next="))
        self.assertIn("%2Fplatform%2Ftenants%2F", login_url)

    def test_safe_next_url_accepts_same_host_path(self):
        request = self.factory.get("/platform/login/?next=/platform/tenants/", HTTP_HOST="example.com")

        self.assertEqual(_safe_next_url(request), "/platform/tenants/")

    def test_safe_next_url_rejects_external_host(self):
        request = self.factory.get("/platform/login/?next=https://evil.example/phish", HTTP_HOST="example.com")

        self.assertIsNone(_safe_next_url(request))


class DomainInputTests(SimpleTestCase):
    def test_domain_input_is_normalized_for_non_technical_entry(self):
        self.assertEqual(normalize_domain("HTTPS://School.Example.Com/"), "school.example.com")
        self.assertEqual(normalize_domain("  http://portal.school.ac.ug  "), "portal.school.ac.ug")
