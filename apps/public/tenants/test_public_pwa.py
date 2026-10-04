from django.test import TestCase
from django.urls import reverse


class PublicPwaReadinessTests(TestCase):
    def test_public_readiness_does_not_require_tenant_push_table(self):
        response = self.client.get(reverse("pwa_push_readiness"), HTTP_HOST="edumanage.leosoftug.com")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["subscription_storage_ready"])
        self.assertEqual(payload["active_subscriptions"], 0)
