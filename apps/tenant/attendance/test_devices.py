from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.finance.integration_services import process_biometric_event
from apps.tenant.finance.models import BiometricDevice
from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Notification
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import User

from .device_services import ingest_payload, reprocess_unmatched_identity
from .models import (
    AttendanceDailyRecord,
    AttendanceDevice,
    AttendanceEvent,
    AttendanceIdentity,
    AttendancePolicy,
)


class UniversalAttendanceDeviceTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = org.campuses.filter(is_default=True).first() or org.campuses.first()
        if self.campus is None:
            self.campus = org.campuses.create(name="Main Campus", code="MAIN", is_default=True, is_active=True)

        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="STU-0042",
            first_name="Amina",
            last_name="Learner",
            is_active=True,
        )
        self.staff = StaffProfile.objects.create(
            campus=self.campus,
            staff_id="EMP-009",
            first_name="Grace",
            last_name="Teacher",
            is_active=True,
        )
        self.device = AttendanceDevice.objects.create(
            name="Main Gate",
            code="GATE-MAIN-01",
            campus=self.campus,
            vendor=AttendanceDevice.GENERIC,
            identity_namespace="main-campus-clock",
            timezone_name="Africa/Kampala",
            settings={"max_future_clock_skew_seconds": 300, "use_server_time_on_future_skew": True},
        )
        self.token = self.device.rotate_token()
        self.student_identity = AttendanceIdentity.objects.create(
            namespace=self.device.identity_namespace,
            external_person_id="42",
            person_type=AttendanceIdentity.STUDENT,
            student=self.student,
            source="TEST",
        )
        self.staff_identity = AttendanceIdentity.objects.create(
            namespace=self.device.identity_namespace,
            external_person_id="9",
            person_type=AttendanceIdentity.STAFF,
            staff=self.staff,
            source="TEST",
        )
        AttendancePolicy.objects.create(
            name="Student gate day",
            campus=self.campus,
            person_type=AttendanceIdentity.STUDENT,
            expected_in=timezone.datetime(2026, 1, 1, 7, 45).time(),
            expected_out=timezone.datetime(2026, 1, 1, 16, 0).time(),
            duplicate_window_seconds=90,
            direction_strategy=AttendancePolicy.FIRST_LAST,
            is_default=True,
            is_active=True,
        )
        AttendancePolicy.objects.create(
            name="Staff working day",
            campus=self.campus,
            person_type=AttendanceIdentity.STAFF,
            expected_in=timezone.datetime(2026, 1, 1, 8, 0).time(),
            expected_out=timezone.datetime(2026, 1, 1, 17, 0).time(),
            duplicate_window_seconds=90,
            direction_strategy=AttendancePolicy.FIRST_LAST,
            is_default=True,
            is_active=True,
        )

    def post_event(self, payload, token=None):
        return self.client.post(
            reverse("api_attendance_device_events"),
            data=payload,
            content_type="application/json",
            HTTP_X_DEVICE_CODE=self.device.code,
            HTTP_X_DEVICE_KEY=token if token is not None else self.token,
        )

    def test_device_api_rejects_invalid_secret(self):
        response = self.post_event({"person_id": "42", "timestamp": timezone.now().isoformat()}, token="wrong-key")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(AttendanceEvent.objects.count(), 0)

    def test_student_event_creates_raw_event_and_daily_presence_without_class_attendance(self):
        stamp = timezone.now().replace(microsecond=0)
        response = self.post_event(
            {
                "event_id": "evt-1",
                "person_id": "42",
                "timestamp": stamp.isoformat(),
                "direction": "IN",
                "auth_method": "FACE",
            }
        )
        self.assertEqual(response.status_code, 200)
        item = AttendanceEvent.objects.get()
        self.assertEqual(item.processing_status, AttendanceEvent.PROCESSED)
        self.assertEqual(item.student, self.student)
        self.assertEqual(item.auth_method, AttendanceEvent.FACE)
        record = AttendanceDailyRecord.objects.get(student=self.student, date=stamp.astimezone(timezone.get_current_timezone()).date())
        self.assertEqual(record.source_event_count, 1)
        self.assertIsNotNone(record.first_in)
        self.assertEqual(record.last_out, None)
        self.assertTrue(record.open_presence)
        from .models import AttendanceSession
        self.assertEqual(AttendanceSession.objects.count(), 0)

    def test_exact_replay_is_idempotent(self):
        stamp = timezone.now().replace(microsecond=0)
        payload = {"event_id": "evt-replay-1", "person_id": "42", "timestamp": stamp.isoformat()}
        first = self.post_event(payload)
        second = self.post_event(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(AttendanceEvent.objects.count(), 1)
        self.assertFalse(second.json()["results"][0]["created"])

    def test_near_duplicate_scan_is_preserved_but_does_not_change_daily_evidence_count(self):
        stamp = timezone.now().replace(microsecond=0)
        first, _ = ingest_payload(
            device=self.device,
            payload={"event_id": "near-1", "person_id": "42", "timestamp": stamp.isoformat()},
        )
        second, _ = ingest_payload(
            device=self.device,
            payload={"event_id": "near-2", "person_id": "42", "timestamp": (stamp + timedelta(seconds=20)).isoformat()},
        )
        self.assertEqual(first.processing_status, AttendanceEvent.PROCESSED)
        self.assertEqual(second.processing_status, AttendanceEvent.DUPLICATE)
        record = AttendanceDailyRecord.objects.get(student=self.student)
        self.assertEqual(record.source_event_count, 1)
        self.assertEqual(AttendanceEvent.objects.count(), 2)

    def test_unmatched_event_can_be_recovered_after_identity_mapping(self):
        stamp = timezone.now().replace(microsecond=0)
        event, _ = ingest_payload(
            device=self.device,
            payload={"event_id": "unknown-1", "person_id": "NEW-USER", "timestamp": stamp.isoformat()},
        )
        self.assertEqual(event.processing_status, AttendanceEvent.UNMATCHED)
        identity = AttendanceIdentity.objects.create(
            namespace=self.device.identity_namespace,
            external_person_id="NEW-USER",
            person_type=AttendanceIdentity.STUDENT,
            student=self.student,
            source="TEST",
        )
        processed = reprocess_unmatched_identity(identity)
        event.refresh_from_db()
        self.assertEqual(processed, 1)
        self.assertEqual(event.processing_status, AttendanceEvent.PROCESSED)
        self.assertEqual(event.student, self.student)
        self.assertTrue(AttendanceDailyRecord.objects.filter(student=self.student, date=stamp.astimezone(timezone.get_current_timezone()).date()).exists())

    def test_first_last_strategy_uses_first_and_last_accepted_punch(self):
        tz = timezone.get_current_timezone()
        day = timezone.localdate()
        first = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime(2026, 1, 1, 7, 30).time()), timezone=tz)
        last = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime(2026, 1, 1, 16, 15).time()), timezone=tz)
        ingest_payload(device=self.device, payload={"event_id": "day-in", "person_id": "42", "timestamp": first.isoformat()})
        ingest_payload(device=self.device, payload={"event_id": "day-out", "person_id": "42", "timestamp": last.isoformat()})
        record = AttendanceDailyRecord.objects.get(student=self.student, date=day)
        self.assertEqual(record.first_in, first)
        self.assertEqual(record.last_out, last)
        self.assertEqual(record.minutes_present, 525)
        self.assertFalse(record.open_presence)

    def test_staff_identity_creates_staff_daily_record(self):
        stamp = timezone.now().replace(microsecond=0)
        event, _ = ingest_payload(
            device=self.device,
            payload={"event_id": "staff-1", "person_id": "9", "timestamp": stamp.isoformat(), "auth_method": "fingerprint"},
        )
        self.assertEqual(event.processing_status, AttendanceEvent.PROCESSED)
        self.assertEqual(event.staff, self.staff)
        record = AttendanceDailyRecord.objects.get(staff=self.staff)
        self.assertEqual(record.person_type, AttendanceIdentity.STAFF)

    def test_future_clock_timestamp_can_fall_back_to_server_arrival_time(self):
        future = timezone.now() + timedelta(hours=6)
        event, _ = ingest_payload(
            device=self.device,
            payload={"event_id": "future-1", "person_id": "42", "timestamp": future.isoformat()},
        )
        self.assertTrue(event.server_time_used)
        self.assertLess(abs((event.occurred_at - event.received_at).total_seconds()), 2)

    def test_parent_arrival_notification_is_sent_once(self):
        policy = AttendancePolicy.objects.get(person_type=AttendanceIdentity.STUDENT, campus=self.campus)
        policy.notify_parent_on_arrival = True
        policy.save(update_fields=["notify_parent_on_arrival", "updated_at"])
        parent_user = User.objects.create_user(username="arrival-parent", password="test-pass-123")
        parent = ParentProfile.objects.create(user=parent_user, first_name="Pat", last_name="Parent")
        ParentStudentLink.objects.create(parent=parent, student=self.student, is_primary=True)
        stamp = timezone.now().replace(microsecond=0)
        ingest_payload(device=self.device, payload={"event_id": "arrival-1", "person_id": "42", "timestamp": stamp.isoformat(), "direction": "IN"})
        ingest_payload(device=self.device, payload={"event_id": "arrival-2", "person_id": "42", "timestamp": (stamp + timedelta(minutes=3)).isoformat(), "direction": "IN"})
        self.assertEqual(Notification.objects.filter(recipient=parent_user, title="Arrival recorded").count(), 1)

    def test_legacy_biometric_service_uses_universal_daily_presence_without_requiring_offering(self):
        legacy = BiometricDevice.objects.create(name="Legacy Main", device_code="LEGACY-MAIN", campus=self.campus, is_active=True)
        stamp = timezone.now().replace(microsecond=0)
        old_event = process_biometric_event(
            {
                "device_code": legacy.device_code,
                "person_id": self.student.student_id,
                "event_id": "legacy-evt-1",
                "timestamp": stamp.isoformat(),
            }
        )
        self.assertTrue(old_event.processed)
        self.assertEqual(old_event.student, self.student)
        self.assertIsNone(old_event.attendance_entry)
        self.assertTrue(AttendanceEvent.objects.filter(source=AttendanceEvent.LEGACY, student=self.student).exists())
        self.assertTrue(AttendanceDailyRecord.objects.filter(student=self.student).exists())
