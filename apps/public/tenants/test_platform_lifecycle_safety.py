from django.test import TestCase
from django.urls import reverse

from apps.public.tenants.models import Domain, SubscriptionPlan, Tenant, TenantSubscription
from apps.tenant.users.models import User


class PlatformLifecycleSafetyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", email="owner@example.com", password="StrongPass123!")
        self.client.force_login(self.owner)
        session = self.client.session
        session["platform_2fa_verified"] = True
        session.save()
        self.tenant = Tenant.objects.create(schema_name="lifecycle_school", name="Lifecycle School", status="suspended")
        self.domain = Domain.objects.create(tenant=self.tenant, domain="lifecycle.example.com", is_primary=True)
        plan = SubscriptionPlan.objects.create(code="standard", name="Standard", monthly_price=1, annual_price=1)
        self.subscription = TenantSubscription.objects.create(tenant=self.tenant, plan=plan, status=TenantSubscription.SUSPENDED)

    def test_non_usable_subscription_blocks_manual_reactivation(self):
        response = self.client.post(reverse("platform_tenant_status_update", args=[self.tenant.pk]), {"status": "active", "reason": "support request"})
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, "suspended")
        self.assertEqual(response.status_code, 302)

    def test_only_primary_domain_cannot_be_deleted(self):
        response = self.client.post(reverse("platform_domain_delete", args=[self.domain.pk]))
        self.assertTrue(Domain.objects.filter(pk=self.domain.pk).exists())
        self.assertEqual(response.status_code, 302)
