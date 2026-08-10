from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization

from .models import AttendanceDevice


class AttendanceDeviceCreationFlowTests(TestCase):
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
        self.admin = get_user_model().objects.create_superuser(
            username="attendance-create-admin",
            email="attendance-create@example.test",
            password="StrongPass123!",
        )
        self.client.force_login(self.admin)

    def test_new_device_redirects_directly_to_guided_setup_with_one_time_key_in_session(self):
        response = self.client.post(
            reverse("admin_attendance_device_create"),
            {
                "name": "Front Gate Reader",
                "code": "FRONT-GATE-01",
                "serial_number": "",
                "vendor": AttendanceDevice.GENERIC,
                "model_name": "",
                "campus": self.campus.pk,
                "location": "Front gate",
                "connection_mode": AttendanceDevice.PUSH,
                "protocol": "canonical-json",
                "identity_namespace": "front-gate",
                "timezone_name": "Africa/Kampala",
                "capabilities": "{}",
                "settings": "{}",
                "is_active": "on",
            },
        )
        device = AttendanceDevice.objects.get(code="FRONT-GATE-01")
        self.assertRedirects(
            response,
            reverse("admin_attendance_device_setup", args=[device.pk]),
            fetch_redirect_response=False,
        )
        token_payload = self.client.session.get("attendance_device_token")
        self.assertIsNotNone(token_payload)
        self.assertEqual(token_payload["device_id"], device.pk)
        self.assertTrue(token_payload["token"])
        self.assertTrue(device.token_hash)
