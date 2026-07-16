from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import normalize_domain
from .middleware import TenantStatusMiddleware
from .models import Domain, PlatformAuditEvent, Tenant
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


class CreateSchoolWizardOnboardingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.platform_admin = User.objects.create_superuser(
            username="platform_admin",
            email="platform@example.com",
            password="platform-pass-123",
        )
        self.client.force_login(self.platform_admin)

    def _post_step(self, step, data):
        payload = {"step": step, **data}
        return self.client.post(f"{reverse('platform_tenant_create')}?step={step}", payload)

    def test_wizard_creates_complete_school_owner_handoff(self):
        self._post_step(
            "school",
            {
                "name": "Bright Future Academy",
                "schema_name": "bright_future",
                "status": "active",
                "organization_email": "office@brightfuture.test",
                "organization_phone": "+256700000001",
                "organization_address": "Plot 1 School Road",
            },
        )
        self._post_step(
            "domain",
            {
                "domain": "portal.brightfuture.test",
                "domain_type": Domain.CUSTOM,
            },
        )
        self._post_step(
            "owner",
            {
                "owner_first_name": "Amina",
                "owner_last_name": "Owner",
                "owner_email": "owner@brightfuture.test",
                "owner_phone": "+256700000002",
                "owner_username": "",
                "owner_temporary_password": "OwnerPass123!",
                "owner_temporary_password_confirm": "OwnerPass123!",
            },
        )
        self._post_step(
            "features",
            {
                "package": "standard",
                "feature_flags": ["academics", "attendance"],
            },
        )

        response = self._post_step("confirm", {"confirm_activation": "on"})

        tenant = Tenant.objects.get(schema_name="bright_future")
        self.assertRedirects(response, reverse("platform_tenant_detail", args=[tenant.pk]))
        domain = Domain.objects.get(tenant=tenant, is_primary=True)
        self.assertEqual(domain.domain, "portal.brightfuture.test")
        self.assertEqual(tenant.subscription.plan.code, "standard")

        created_event = PlatformAuditEvent.objects.get(
            tenant=tenant,
            action=PlatformAuditEvent.TENANT_CREATED,
        )
        self.assertEqual(created_event.metadata["admin_username"], "bright_future_admin")
        self.assertEqual(created_event.metadata["login_url"], "https://portal.brightfuture.test/login/")
        self.assertEqual(
            created_event.metadata["setup_guide_url"],
            "https://portal.brightfuture.test/admin/school-setup/",
        )
        self.assertTrue(created_event.metadata["feature_flags_total"] >= 1)

    def test_tenant_detail_shows_owner_handoff_pack(self):
        tenant = Tenant.objects.create(name="Ready School", schema_name="ready_school", status="active")
        domain = Domain.objects.create(
            tenant=tenant,
            domain="ready.school.test",
            type=Domain.CUSTOM,
            is_primary=True,
            dns_status=Domain.DNS_VERIFIED,
            ssl_status=Domain.SSL_ACTIVE,
        )
        PlatformAuditEvent.objects.create(
            actor=self.platform_admin,
            tenant=tenant,
            domain=domain,
            action=PlatformAuditEvent.TENANT_CREATED,
            object_label=tenant.name,
            metadata={
                "admin_username": "ready_school_admin",
                "login_domain": "ready.school.test",
                "login_url": "https://ready.school.test/login/",
                "setup_guide_url": "https://ready.school.test/admin/school-setup/",
            },
        )

        response = self.client.get(reverse("platform_tenant_detail", args=[tenant.pk]))

        self.assertContains(response, "School owner handoff")
        self.assertContains(response, "ready_school_admin")
        self.assertContains(response, "https://ready.school.test/login/")
        self.assertContains(response, "https://ready.school.test/admin/school-setup/")
