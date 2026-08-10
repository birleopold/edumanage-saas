from django.test import TestCase
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .device_services import ingest_payload
from .models import AttendanceDevice, AttendanceIdentity
from .payload_privacy import REDACTED


class AttendancePayloadPrivacyTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org, is_default=True).first() or Campus.objects.filter(organization=org).first()
        if self.campus is None:
            self.campus = Campus.objects.create(
                organization=org,
                name="Main Campus",
                code="MAIN",
                is_default=True,
                is_active=True,
            )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="PRIV-001",
            first_name="Privacy",
            last_name="Learner",
        )
        self.device = AttendanceDevice.objects.create(
            name="Privacy Gate",
            code="PRIVACY-GATE",
            campus=self.campus,
            identity_namespace="privacy-gate-users",
        )
        AttendanceIdentity.objects.create(
            namespace=self.device.identity_namespace,
            external_person_id="1",
            person_type=AttendanceIdentity.STUDENT,
            student=self.student,
        )

    def test_biometric_material_is_redacted_from_raw_event_evidence(self):
        event, _ = ingest_payload(
            device=self.device,
            payload={
                "event_id": "privacy-event-1",
                "person_id": "1",
                "timestamp": timezone.now().isoformat(),
                "auth_method": "FACE",
                "face_template": "very-sensitive-template",
                "image": "base64-image-data",
                "nested": {"fingerprint_template": "finger-template", "terminal": "Gate 1"},
            },
        )
        event.refresh_from_db()
        self.assertEqual(event.raw_payload["face_template"], REDACTED)
        self.assertEqual(event.raw_payload["image"], REDACTED)
        self.assertEqual(event.raw_payload["nested"]["fingerprint_template"], REDACTED)
        self.assertEqual(event.raw_payload["nested"]["terminal"], "Gate 1")
        self.assertEqual(event.external_person_id, "1")
