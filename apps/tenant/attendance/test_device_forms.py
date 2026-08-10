from django.test import TestCase

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization

from .device_forms import AttendanceDeviceForm
from .models import AttendanceDevice


class AttendanceDeviceConfigurationTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.main = Campus.objects.filter(organization=org, is_default=True).first() or Campus.objects.filter(organization=org).first()
        if self.main is None:
            self.main = Campus.objects.create(
                organization=org,
                name="Main Campus",
                code="MAIN",
                is_default=True,
                is_active=True,
            )
        self.other = Campus.objects.create(
            organization=org,
            name="Other Campus",
            code="OTHER",
            is_active=True,
        )
        AttendanceDevice.objects.create(
            name="Main Gate",
            code="MAIN-GATE",
            campus=self.main,
            identity_namespace="shared-campus-users",
            vendor=AttendanceDevice.GENERIC,
            connection_mode=AttendanceDevice.PUSH,
            timezone_name="Africa/Kampala",
        )

    def device_data(self, *, code, campus):
        return {
            "name": code.replace("-", " ").title(),
            "code": code,
            "serial_number": "",
            "vendor": AttendanceDevice.GENERIC,
            "model_name": "",
            "campus": str(campus.pk),
            "location": "Gate",
            "connection_mode": AttendanceDevice.PUSH,
            "protocol": "canonical-json",
            "identity_namespace": "shared-campus-users",
            "timezone_name": "Africa/Kampala",
            "capabilities": "{}",
            "settings": "{}",
            "is_active": "on",
        }

    def test_same_namespace_is_allowed_for_multiple_devices_in_same_campus(self):
        form = AttendanceDeviceForm(data=self.device_data(code="SECOND-MAIN-GATE", campus=self.main))
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_same_namespace_is_blocked_across_campuses(self):
        form = AttendanceDeviceForm(data=self.device_data(code="OTHER-GATE", campus=self.other))
        self.assertFalse(form.is_valid())
        self.assertIn("identity_namespace", form.errors)
        self.assertIn("prevent user-ID collisions", form.errors["identity_namespace"][0])
