from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Domain, Tenant
from .subscription_services import create_subscription_for_tenant


class PlatformConsoleUiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.platform_admin = User.objects.create_superuser(
            username="platform_ui_admin",
            email="platform-ui@example.test",
            password="StrongPlatformPass123!",
        )
        cls.tenant = Tenant.objects.create(
            name="Platform UI School",
            schema_name="platform_ui_school",
            status="active",
        )
        cls.domain = Domain.objects.create(
            tenant=cls.tenant,
            domain="platform-ui-school.example.test",
            type=Domain.CUSTOM,
            is_primary=True,
            dns_status=Domain.DNS_VERIFIED,
            ssl_status=Domain.SSL_ACTIVE,
        )
        create_subscription_for_tenant(cls.tenant)

    def setUp(self):
        self.client.force_login(self.platform_admin)

    def assert_platform_workspace(self, route_name, marker, *, kwargs=None):
        response = self.client.get(reverse(route_name, kwargs=kwargs or {}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, marker)
        self.assertContains(response, "platform-console.css")
        self.assertContains(response, "platform-console.js")
        return response

    def test_primary_platform_workspaces_render(self):
        expectations = [
            ("platform_dashboard", "Domain readiness", None),
            ("platform_tenant_list", "School register", None),
            ("platform_activity", "Audit timeline", None),
            ("platform_subscription_dashboard", "Subscription register", None),
            ("platform_deployment_readiness", "Environment configuration", None),
            ("platform_tenant_detail", "Owner handoff", {"pk": self.tenant.pk}),
            ("platform_tenant_subscription", "Usage and limits", {"tenant_id": self.tenant.pk}),
        ]

        for route_name, marker, kwargs in expectations:
            with self.subTest(route_name=route_name):
                self.assert_platform_workspace(route_name, marker, kwargs=kwargs)

    def test_tenant_list_honours_page_size_and_status_filters(self):
        response = self.client.get(
            reverse("platform_tenant_list"),
            {"status": "active", "per_page": "10", "q": "Platform UI"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["per_page"], 10)
        self.assertEqual(response.context["status"], "active")
        self.assertContains(response, self.tenant.name)
        self.assertContains(response, self.domain.domain)

    def test_subscription_filters_are_preserved(self):
        response = self.client.get(
            reverse("platform_subscription_dashboard"),
            {"status": "trialing", "payment": "unpaid", "q": "Platform UI"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], "trialing")
        self.assertEqual(response.context["selected_payment"], "unpaid")
        self.assertContains(response, self.tenant.name)
