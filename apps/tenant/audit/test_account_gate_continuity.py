from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.models import Role, User

from .guards import AdminTwoFactorGuard
from .models import ConsentRecord
from .request_log import RequestLogMiddleware


@override_settings(PRIVACY_ACCEPTANCE_REQUIRED=True, PRIVACY_POLICY_VERSION="2026.1")
class PrivacyAndTwoFactorContinuityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = OrganizationProfile.objects.create(name="Account Gate School")
        Campus.objects.create(
            organization=organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
        )
        cls.roles = {
            code: Role.objects.get_or_create(code=code, defaults={"name": label})[0]
            for code, label in Role.CODE_CHOICES
        }
        cls.parent = User.objects.create_user(username="parent-gate", password="StrongPass123!")
        cls.parent.roles.add(cls.roles[Role.PARENT])
        cls.principal = User.objects.create_user(
            username="principal-gate",
            password="StrongPass123!",
            email="principal@example.com",
        )
        cls.principal.roles.add(cls.roles[Role.PRINCIPAL])

    def setUp(self):
        self.factory = RequestFactory()

    def test_active_middleware_preserves_original_destination(self):
        request = self.factory.get("/parent/finance/?status=overdue")
        request.user = self.parent
        request.session = {}
        response = RequestLogMiddleware(lambda _request: HttpResponse("ok"))(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("audit_privacy_accept")))
        self.assertIn("next=%2Fparent%2Ffinance%2F%3Fstatus%3Doverdue", response.url)

    def test_privacy_accept_page_is_exempt_and_uses_parent_shell(self):
        self.client.force_login(self.parent)
        target = reverse("audit_privacy_accept") + "?next=/parent/"
        response = self.client.get(target)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portals/parent/base.html")
        self.assertTemplateNotUsed(response, "portals/admin/base.html")

    def test_acceptance_is_idempotent_and_returns_to_safe_destination(self):
        self.client.force_login(self.parent)
        url = reverse("audit_privacy_accept")

        first = self.client.post(url, {"next": "/parent/"})
        second = self.client.post(url, {"next": "/parent/"})

        self.assertRedirects(first, "/parent/", fetch_redirect_response=False)
        self.assertRedirects(second, "/parent/", fetch_redirect_response=False)
        self.assertEqual(
            ConsentRecord.objects.filter(
                user=self.parent,
                consent_type=ConsentRecord.PRIVACY,
                version="2026.1",
            ).count(),
            1,
        )

    def test_external_return_target_falls_back_to_parent_home(self):
        self.client.force_login(self.parent)
        response = self.client.post(
            reverse("audit_privacy_accept"),
            {"next": "https://attacker.example/steal"},
        )
        self.assertRedirects(response, reverse("parent_home"), fetch_redirect_response=False)

    @override_settings(PRIVACY_ACCEPTANCE_REQUIRED=False)
    def test_non_admin_cannot_open_verification_flow(self):
        self.client.force_login(self.parent)
        response = self.client.get(reverse("audit_verify_2fa"))
        self.assertEqual(response.status_code, 403)

    @patch("apps.tenant.audit.guards.user_needs_2fa", return_value=True)
    def test_two_factor_guard_does_not_redirect_verification_page_to_itself(self, _needs_2fa):
        middleware = AdminTwoFactorGuard(lambda _request: HttpResponse("ok"))

        verify_request = self.factory.get(reverse("audit_verify_2fa"))
        verify_request.user = self.principal
        verify_request.session = {}
        self.assertEqual(middleware(verify_request).status_code, 200)

        admin_request = self.factory.get("/admin/")
        admin_request.user = self.principal
        admin_request.session = {}
        response = middleware(admin_request)
        self.assertRedirects(
            response,
            reverse("audit_verify_2fa"),
            fetch_redirect_response=False,
        )
