import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.tenant.audit.models import ConsentRecord
from apps.tenant.portals.models import WebPushSubscription
from apps.tenant.portals.push_delivery import send_web_push, send_web_push_to_user
from apps.tenant.users.models import Role, User


def accept_privacy_for(user):
    ConsentRecord.objects.create(user=user, consent_type=ConsentRecord.PRIVACY, accepted=True, version="1.0")


class PwaPushEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pwa_user", password="test-pass-123")
        accept_privacy_for(self.user)

    def test_subscribe_saves_browser_subscription_for_signed_in_user(self):
        self.client.login(username="pwa_user", password="test-pass-123")
        response = self.client.post(
            reverse("pwa_push_subscribe"),
            data=json.dumps(
                {
                    "endpoint": "https://push.example.test/subscription/1",
                    "keys": {"p256dh": "public-key", "auth": "auth-secret"},
                }
            ),
            content_type="application/json",
            HTTP_USER_AGENT="Django Test Browser",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active_subscriptions"], 1)
        subscription = WebPushSubscription.objects.get()
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.p256dh_key, "public-key")
        self.assertEqual(subscription.auth_key, "auth-secret")
        self.assertEqual(subscription.user_agent, "Django Test Browser")
        self.assertTrue(subscription.is_active)

    def test_unsubscribe_disables_only_matching_active_subscription(self):
        self.client.login(username="pwa_user", password="test-pass-123")
        target = WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/target",
            p256dh_key="public-key",
            auth_key="auth-secret",
            is_active=True,
        )
        other = WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/other",
            p256dh_key="public-key",
            auth_key="auth-secret",
            is_active=True,
        )

        response = self.client.post(
            reverse("pwa_push_unsubscribe"),
            data=json.dumps({"endpoint": target.endpoint}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["disabled"], 1)
        target.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertTrue(other.is_active)

    def test_subscribe_rejects_payload_without_browser_push_keys(self):
        self.client.login(username="pwa_user", password="test-pass-123")
        response = self.client.post(
            reverse("pwa_push_subscribe"),
            data=json.dumps({"endpoint": "https://push.example.test/subscription/no-keys"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Missing browser push keys.")
        self.assertFalse(WebPushSubscription.objects.exists())

    def test_push_delivery_returns_skipped_when_vapid_private_key_is_missing(self):
        subscription = WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/1",
            p256dh_key="public-key",
            auth_key="auth-secret",
            is_active=True,
        )

        with mock.patch("apps.tenant.portals.push_delivery.config", return_value=""):
            result = send_web_push(subscription, title="Test", body="Body")

        self.assertFalse(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertIn("WEB_PUSH_PRIVATE_KEY", result["reason"])

    def test_user_push_delivery_skips_incomplete_subscriptions(self):
        WebPushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/missing-keys",
            is_active=True,
        )

        with mock.patch("apps.tenant.portals.push_delivery.send_web_push") as send_single:
            result = send_web_push_to_user(self.user, title="Test", body="Body")

        self.assertEqual(result["attempted"], 0)
        self.assertEqual(result["sent"], 0)
        send_single.assert_not_called()


class PwaOfflineAttendanceShellTests(TestCase):
    def test_service_worker_precaches_offline_attendance_assets(self):
        response = self.client.get(reverse("pwa_service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        content = response.content.decode("utf-8")
        self.assertIn("/static/js/offline-attendance.js", content)
        self.assertIn("/static/css/mobile-pwa.css", content)
        self.assertIn('const CACHE_NAME = "edumanage-static-v2";', content)

    def test_service_worker_keeps_teacher_attendance_pages_available_after_visit(self):
        response = self.client.get(reverse("pwa_service_worker"))

        content = response.content.decode("utf-8")
        self.assertIn('url.pathname.startsWith("/teacher/attendance/roll-call/")', content)
        self.assertIn('url.pathname.startsWith("/teacher/attendance/take/")', content)
        self.assertIn("cache.put(request, copy)", content)
        self.assertIn("cached || new Response(OFFLINE_HTML", content)

    def test_manifest_is_mobile_install_ready_for_teacher_workflows(self):
        response = self.client.get(reverse("pwa_manifest"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["display"], "standalone")
        self.assertEqual(payload["orientation"], "portrait-primary")
        self.assertEqual(payload["scope"], "/")
        self.assertTrue(any(icon["src"] == "/static/img/pwa-icon.svg" for icon in payload["icons"]))


class AdminPwaPushTests(TestCase):
    def setUp(self):
        self.admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin"})
        self.admin = User.objects.create_user(username="pwa_admin", password="test-pass-123")
        self.admin.roles.add(self.admin_role)
        accept_privacy_for(self.admin)

    def test_admin_test_push_uses_signed_in_admin(self):
        self.client.login(username="pwa_admin", password="test-pass-123")

        with mock.patch("apps.tenant.users.device_portal.send_web_push_to_user") as send_to_user:
            send_to_user.return_value = {"sent": 1, "attempted": 1, "results": [{"ok": True}]}
            response = self.client.post(reverse("admin_user_devices_test_push"))

        self.assertRedirects(response, reverse("admin_user_devices"))
        send_to_user.assert_called_once_with(
            self.admin,
            title="EduManage test alert",
            body="PWA alerts are working for your account.",
            url="/admin/users/devices/",
        )
