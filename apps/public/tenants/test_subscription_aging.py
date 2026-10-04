from datetime import timedelta
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from apps.public.tenants.models import SubscriptionPlan, Tenant, TenantSubscription

class SubscriptionAgingPublicSchemaTests(TestCase):
    def test_public_schema_subscription_is_never_aged(self):
        plan=SubscriptionPlan.objects.create(code="standard",name="Standard",monthly_price=1,annual_price=1)
        tenant=Tenant.objects.create(schema_name="public",name="EduManage Platform",status="active")
        sub=TenantSubscription.objects.create(tenant=tenant,plan=plan,status=TenantSubscription.TRIALING,trial_end=timezone.localdate()-timedelta(days=1),next_billing_date=timezone.localdate()-timedelta(days=1))
        call_command("reconcile_subscriptions")
        sub.refresh_from_db()
        self.assertEqual(sub.status,TenantSubscription.TRIALING)
