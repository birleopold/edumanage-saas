from django.test import TestCase
from django.urls import reverse

from apps.public.tenants.models import Domain, Tenant


class CaddyDomainPermissionTests(TestCase):
    def setUp(self):
        self.active = Tenant.objects.create(schema_name="tls_active", name="TLS Active", status="active")
        self.suspended = Tenant.objects.create(schema_name="tls_suspended", name="TLS Suspended", status="suspended")
        Domain.objects.create(tenant=self.active, domain="portal.active-school.example", is_primary=True)
        Domain.objects.create(tenant=self.suspended, domain="portal.suspended-school.example", is_primary=True)

    def test_registered_active_domain_is_allowed(self):
        response = self.client.get(reverse("caddy_domain_permission"), {"domain": "portal.active-school.example"})
        self.assertEqual(response.status_code, 200)

    def test_unknown_domain_is_denied(self):
        response = self.client.get(reverse("caddy_domain_permission"), {"domain": "attacker.example"})
        self.assertEqual(response.status_code, 404)

    def test_suspended_tenant_domain_is_denied(self):
        response = self.client.get(reverse("caddy_domain_permission"), {"domain": "portal.suspended-school.example"})
        self.assertEqual(response.status_code, 404)

    def test_lookup_is_case_insensitive_and_accepts_trailing_dot(self):
        response = self.client.get(reverse("caddy_domain_permission"), {"domain": "PORTAL.ACTIVE-SCHOOL.EXAMPLE."})
        self.assertEqual(response.status_code, 200)
