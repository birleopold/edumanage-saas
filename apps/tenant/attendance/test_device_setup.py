from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, UserRole

from .device_setup import recommended_setup
from .models import AttendanceDevice


class AttendanceDeviceSetupPageTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = organization.campuses.filter(is_default=True).first()
        if self.campus is None:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                code="MAIN",
                is_default=True,
                is_active=True,
            )
        self.device = AttendanceDevice.objects.create(
            name="Main Gate Clock",
            code="MAIN-GATE-01",
            campus=self.campus,
            vendor=AttendanceDevice.ZKTECO,
            connection_mode=AttendanceDevice.PUSH,
            identity_namespace="main-campus-clock",
            timezone_name="Africa/Kampala",
        )
        self.device.rotate_token()
        self.admin = get_user_model().objects.create_superuser(
            username="attendance-setup-admin",
            email="attendance-setup@example.test",
            password="StrongPass123!",
        )
        self.client.force_login(self.admin)

    def test_setup_page_calculates_tenant_endpoints(self):
        response = self.client.get(
            reverse("admin_attendance_device_setup", args=[self.device.pk]),
            HTTP_HOST="example.com",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect Main Gate Clock without server access")
        self.assertContains(response, "example.com")
        self.assertContains(response, "/api/v1/attendance/devices/events/")
        self.assertContains(response, "/api/v1/attendance/devices/heartbeat/")
        self.assertContains(response, self.device.code)
        self.assertContains(response, "Calculated automatically")
        self.assertContains(response, "Edge Connector recommended")

    def test_proprietary_vendor_requires_explicit_canonical_push_capability(self):
        self.assertEqual(recommended_setup(self.device)["kind"], "edge")
        self.device.protocol = "canonical-json"
        self.device.save(update_fields=["protocol", "updated_at"])
        self.assertEqual(recommended_setup(self.device)["kind"], "direct")

    def test_generic_webhook_device_defaults_to_direct_https(self):
        generic = AttendanceDevice.objects.create(
            name="Webhook Gate",
            code="WEBHOOK-GATE-01",
            campus=self.campus,
            vendor=AttendanceDevice.GENERIC,
            connection_mode=AttendanceDevice.PUSH,
            identity_namespace="webhook-gate",
        )
        self.assertEqual(recommended_setup(generic)["kind"], "direct")

    def test_rotating_key_shows_new_secret_only_in_response(self):
        previous_hash = self.device.token_hash
        response = self.client.post(
            reverse("admin_attendance_device_setup", args=[self.device.pk]),
            {"action": "rotate_token"},
        )
        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertNotEqual(self.device.token_hash, previous_hash)
        self.assertContains(response, "Copy this device key now")
        self.assertContains(response, self.device.token_prefix)

    def test_edge_config_download_never_contains_device_secret(self):
        response = self.client.get(
            reverse("admin_attendance_device_edge_config", args=[self.device.pk]),
            HTTP_HOST="example.com",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        body = response.content.decode("utf-8")
        self.assertIn('"device_code": "MAIN-GATE-01"', body)
        self.assertIn('"device_key_env": "EDUMANAGE_ATTENDANCE_DEVICE_KEY"', body)
        self.assertNotIn("token_hash", body)
        self.assertNotIn("X-Device-Key", body)

    def test_status_moves_from_waiting_to_online_to_receiving(self):
        status_url = reverse("admin_attendance_device_setup_status", args=[self.device.pk])
        response = self.client.get(status_url)
        self.assertEqual(response.json()["code"], "waiting")

        self.device.last_seen_at = timezone.now()
        self.device.save(update_fields=["last_seen_at", "updated_at"])
        response = self.client.get(status_url)
        self.assertEqual(response.json()["code"], "online")

        self.device.last_event_at = timezone.now()
        self.device.save(update_fields=["last_event_at", "updated_at"])
        response = self.client.get(status_url)
        self.assertEqual(response.json()["code"], "receiving")

    def test_campus_admin_cannot_open_other_campus_device_setup(self):
        other = Campus.objects.create(
            organization=self.campus.organization,
            name="Other Campus",
            code="OTHER",
            is_active=True,
        )
        hidden_device = AttendanceDevice.objects.create(
            name="Other Gate",
            code="OTHER-GATE-01",
            campus=other,
            identity_namespace="other-campus-clock",
        )
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        campus_user = get_user_model().objects.create_user(
            username="attendance-setup-campus-admin",
            password="StrongPass123!",
        )
        UserRole.objects.create(user=campus_user, role=role, campus=self.campus)
        self.client.force_login(campus_user)

        response = self.client.get(reverse("admin_attendance_device_setup", args=[hidden_device.pk]))
        self.assertEqual(response.status_code, 404)

    def test_offline_state_is_reported_after_online_window_expires(self):
        self.device.last_seen_at = timezone.now() - timedelta(hours=1)
        self.device.save(update_fields=["last_seen_at", "updated_at"])
        response = self.client.get(reverse("admin_attendance_device_setup_status", args=[self.device.pk]))
        self.assertEqual(response.json()["code"], "offline")
