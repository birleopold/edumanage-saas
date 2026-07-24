from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Domain, Tenant
from .subscription_services import create_subscription_for_tenant


class PlatformConsoleUiTests(TestCase):
    PLATFORM_PASSWORD = "StrongPlatformPass123!"

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.platform_admin = User.objects.create_superuser(
            username="platform_ui_admin",
            email="platform-ui@example.test",
            password=cls.PLATFORM_PASSWORD,
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
        self.assertContains(response, "platform-layout.css")
        self.assertContains(response, "platform-console.js")
        self.assertContains(response, 'class="platform-workspace"', html=False)
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

    def test_dashboard_uses_compact_metrics_and_explicit_panel_grid(self):
        response = self.client.get(reverse("platform_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "platform-stat__icon")
        self.assertContains(response, "platform-dashboard-columns")
        self.assertContains(response, "platform-stat--teal")

    def test_onboarding_and_maintenance_forms_render(self):
        expectations = [
            ("platform_tenant_create", "Activation creates", None),
            ("platform_tenant_create_classic", "Tenant identity", None),
            ("platform_domain_create", "Domain configuration", {"tenant_id": self.tenant.pk}),
        ]

        for route_name, marker, kwargs in expectations:
            with self.subTest(route_name=route_name):
                response = self.assert_platform_workspace(route_name, marker, kwargs=kwargs)
                self.assertContains(response, "platform-onboarding.css")
                self.assertContains(response, "platform-onboarding.js")

    def test_wizard_navigation_controls_bypass_required_field_validation(self):
        session = self.client.session
        session["platform_create_school_wizard"] = {
            "school": {
                "name": "Saved School",
                "schema_name": "saved_school",
                "status": "active",
                "organization_email": "",
                "organization_phone": "",
                "organization_address": "",
            }
        }
        session.save()

        response = self.client.get(reverse("platform_tenant_create"), {"step": "domain"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="action" value="back" formnovalidate', html=False)
        self.assertContains(response, 'name="action" value="reset" formnovalidate', html=False)

    def test_login_preserves_safe_destination_through_post(self):
        self.client.logout()
        destination = reverse("platform_tenant_list")

        login_page = self.client.get(reverse("platform_admin_login"), {"next": destination})
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, f'name="next" value="{destination}"', html=False)
        self.assertContains(login_page, "platform-onboarding.css")

        response = self.client.post(
            reverse("platform_admin_login"),
            {
                "username": self.platform_admin.username,
                "password": self.PLATFORM_PASSWORD,
                "next": destination,
            },
        )
        self.assertRedirects(response, destination)

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
