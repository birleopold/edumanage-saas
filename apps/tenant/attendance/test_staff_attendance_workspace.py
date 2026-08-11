from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.hr.models import StaffProfile
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization

from .models import AttendanceDailyRecord, AttendanceDevice, AttendanceIdentity, AttendancePolicy


class StaffAttendanceWorkspaceTests(TestCase):
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
        self.staff = StaffProfile.objects.create(
            campus=self.campus,
            staff_id="EMP-001",
            first_name="Jane",
            last_name="Namusoke",
            is_active=True,
        )
        self.policy = AttendancePolicy.objects.create(
            name="Staff working day",
            campus=self.campus,
            person_type=AttendanceIdentity.STAFF,
            expected_in=time(8, 0),
            expected_out=time(17, 0),
            late_grace_minutes=10,
            early_departure_grace_minutes=10,
            weekdays=[0, 1, 2, 3, 4],
            is_default=True,
            is_active=True,
        )
        self.admin = get_user_model().objects.create_superuser(
            username="attendance-admin",
            email="attendance-admin@example.test",
            password="StrongPass123!",
        )
        self.client.force_login(self.admin)

    def test_manual_staff_attendance_does_not_require_device(self):
        self.assertEqual(AttendanceDevice.objects.count(), 0)
        response = self.client.post(
            reverse("admin_attendance_staff_manual"),
            {
                "staff": self.staff.pk,
                "date": "2026-08-10",
                "status": "AUTO",
                "first_in": "08:15",
                "last_out": "16:00",
                "note": "Office attendance register",
                "reason": "Entered from signed staff attendance book",
            },
        )
        self.assertEqual(response.status_code, 302)
        record = AttendanceDailyRecord.objects.get(staff=self.staff, date=date(2026, 8, 10))
        self.assertTrue(record.manual_override)
        self.assertEqual(record.person_type, AttendanceIdentity.STAFF)
        self.assertEqual(record.minutes_late, 15)
        self.assertEqual(record.minutes_early_departure, 60)
        self.assertEqual(record.minutes_present, 465)
        self.assertEqual(record.status, AttendanceDailyRecord.PARTIAL)
        self.assertEqual(record.adjustments.count(), 1)
        self.assertEqual(AttendanceDevice.objects.count(), 0)

    def test_staff_summary_reports_days_attended_and_time_patterns(self):
        AttendanceDailyRecord.objects.create(
            date=date(2026, 8, 3),
            person_type=AttendanceIdentity.STAFF,
            campus=self.campus,
            staff=self.staff,
            policy=self.policy,
            status=AttendanceDailyRecord.PRESENT,
            minutes_present=480,
        )
        AttendanceDailyRecord.objects.create(
            date=date(2026, 8, 4),
            person_type=AttendanceIdentity.STAFF,
            campus=self.campus,
            staff=self.staff,
            policy=self.policy,
            status=AttendanceDailyRecord.ABSENT,
        )
        response = self.client.get(
            reverse("admin_attendance_staff"),
            {"start": "2026-08-03", "end": "2026-08-07"},
        )
        self.assertEqual(response.status_code, 200)
        row = response.context["summaries"][0]
        self.assertEqual(row["expected_days"], 5)
        self.assertEqual(row["days_attended"], 1)
        self.assertEqual(row["days_absent"], 1)
        self.assertEqual(row["attendance_rate"], 20.0)
        self.assertContains(response, "Jane Namusoke")
        self.assertContains(response, "Days attended")

    def test_attendance_dashboard_remains_useful_without_hardware(self):
        response = self.client.get(reverse("admin_attendance_device_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track students and staff with or without biometric devices")
        self.assertContains(response, "Devices are optional")
        self.assertContains(response, "No devices configured")
