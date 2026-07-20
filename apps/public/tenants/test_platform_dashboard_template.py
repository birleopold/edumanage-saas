from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone


@override_settings(ROOT_URLCONF="config.public_urls")
class PlatformDashboardTemplateTests(TestCase):
    def test_system_activity_without_actor_or_tenant_renders_safely(self):
        request = RequestFactory().get("/platform/")
        request.user = AnonymousUser()
        request.resolver_match = SimpleNamespace(url_name="platform_dashboard")

        event = SimpleNamespace(
            actor=None,
            tenant=None,
            tenant_id=None,
            object_label="",
            created_at=timezone.now(),
            get_action_display=lambda: "Tenant created",
        )

        html = render_to_string(
            "platform/dashboard.html",
            {
                "tenant_count": 0,
                "active_count": 0,
                "suspended_count": 0,
                "domain_count": 0,
                "verified_domain_count": 0,
                "tenants": [],
                "domains": [],
                "recent_platform_events": [event],
            },
            request=request,
        )

        self.assertIn("Tenant created", html)
        self.assertIn("System", html)
        self.assertIn("Platform item", html)
