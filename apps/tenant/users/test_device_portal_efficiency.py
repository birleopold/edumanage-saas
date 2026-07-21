from django.test import TestCase

from apps.tenant.portals.models import WebPushSubscription

from .device_portal import base_template_for, device_counts
from .models import Role, User


class DevicePortalEfficiencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="device-monitor-user")

    def test_principal_uses_administrator_portal_explicitly(self):
        principal, _ = Role.objects.get_or_create(
            code=Role.PRINCIPAL,
            defaults={"name": "Principal"},
        )
        self.user.roles.add(principal)

        with self.assertNumQueries(1):
            template = base_template_for(self.user)

        self.assertEqual(template, "portals/admin/base.html")

    def test_device_status_counts_use_one_aggregate_query(self):
        WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example/ready",
            p256dh_key="p256-ready",
            auth_key="auth-ready",
            is_active=True,
        )
        WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example/missing-key",
            p256dh_key="",
            auth_key="",
            is_active=True,
            last_error="Subscription keys are missing.",
        )
        WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example/inactive",
            p256dh_key="p256-inactive",
            auth_key="auth-inactive",
            is_active=False,
        )

        with self.assertNumQueries(1):
            counts = device_counts(WebPushSubscription.objects.all())

        self.assertEqual(
            counts,
            {
                "total_count": 3,
                "active_count": 2,
                "ready_count": 1,
                "error_count": 1,
            },
        )
