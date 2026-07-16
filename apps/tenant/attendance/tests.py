import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course, CourseOffering, Enrollment, Stream
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import AttendanceEntry, AttendanceSession


class OfflineAttendanceSyncTests(TestCase):
    def setUp(self):
        self.role_teacher, _ = Role.objects.get_or_create(code=Role.TEACHER, defaults={"name": "Teacher"})
        self.user = User.objects.create_user(username="offline_teacher", password="test-pass-123")
        self.user.roles.add(self.role_teacher)

        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.teacher = TeacherProfile.objects.create(
            user=self.user,
            campus=self.campus,
            first_name="Offline",
            last_name="Teacher",
        )
        year = AcademicYear.objects.create(name="2026-OFF", is_current=True)
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1, is_current=True)
        course = Course.objects.create(name="Offline Attendance")
        class_group = ClassGroup.objects.create(name="Offline Class", campus=self.campus)
        stream = Stream.objects.create(class_group=class_group, name="A", class_teacher=self.teacher)
        self.student = StudentProfile.objects.create(
            first_name="Offline",
            last_name="Learner",
            campus=self.campus,
            stream=stream,
            student_id="OFF-001",
        )
        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
            teacher=self.teacher,
        )
        Enrollment.objects.create(
            offering=self.offering,
            student=self.student,
            campus=self.campus,
            status=Enrollment.ACTIVE,
        )

    def test_roll_call_save_accepts_replayed_offline_payload(self):
        self.client.login(username="offline_teacher", password="test-pass-123")
        response = self.client.post(
            reverse("teacher_roll_call_save"),
            data=json.dumps(
                {
                    "offering_id": self.offering.id,
                    "date": "2026-07-13",
                    "attendance": {str(self.student.id): AttendanceEntry.ABSENT},
                    "notes": {str(self.student.id): "Synced after reconnect"},
                    "id": f"roll-call:{self.offering.id}:2026-07-13",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        session = AttendanceSession.objects.get(offering=self.offering, date=date(2026, 7, 13))
        entry = AttendanceEntry.objects.get(session=session, student=self.student)
        self.assertEqual(entry.status, AttendanceEntry.ABSENT)
        self.assertEqual(entry.note, "Synced after reconnect")

    def test_roll_call_save_is_idempotent_for_same_class_date_student(self):
        self.client.login(username="offline_teacher", password="test-pass-123")
        url = reverse("teacher_roll_call_save")
        payload = {
            "offering_id": self.offering.id,
            "date": "2026-07-13",
            "attendance": {str(self.student.id): AttendanceEntry.PRESENT},
        }
        self.client.post(url, data=json.dumps(payload), content_type="application/json")
        payload["attendance"][str(self.student.id)] = AttendanceEntry.LATE
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendanceSession.objects.count(), 1)
        self.assertEqual(AttendanceEntry.objects.count(), 1)
        self.assertEqual(AttendanceEntry.objects.get().status, AttendanceEntry.LATE)

    def test_take_attendance_page_includes_offline_queue_wiring(self):
        self.client.login(username="offline_teacher", password="test-pass-123")
        response = self.client.get(
            reverse("teacher_attendance_take"),
            {"offering": self.offering.id, "date": "2026-07-13"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-offline-attendance-form")
        self.assertContains(response, "OfflineAttendanceConfig")
        self.assertContains(response, "offline-attendance.js")


class AttendanceAdminCampusScopeTests(TestCase):
    def setUp(self):
        admin_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="attendance_campus_admin", password="test-pass-123")
        self.user.roles.add(admin_role)

        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Attendance Campus",
            is_active=True,
        )
        UserRole.objects.create(user=self.user, role=admin_role, campus=self.campus)

        year = AcademicYear.objects.create(name="2026-ATT", is_current=True)
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1, is_current=True)
        course = Course.objects.create(name="Attendance Admin")

        class_group = ClassGroup.objects.create(name="Attendance Class", campus=self.campus)
        other_class_group = ClassGroup.objects.create(name="Hidden Attendance Class", campus=self.other_campus)
        teacher = TeacherProfile.objects.create(campus=self.campus, first_name="Visible", last_name="Teacher")
        other_teacher = TeacherProfile.objects.create(campus=self.other_campus, first_name="Hidden", last_name="Teacher")

        self.offering = CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
            teacher=teacher,
        )
        self.other_offering = CourseOffering.objects.create(
            campus=self.other_campus,
            course=course,
            term=term,
            class_group=other_class_group,
            teacher=other_teacher,
        )
        self.session = AttendanceSession.objects.create(offering=self.offering, date=date(2026, 7, 14), taken_by=teacher)
        self.hidden_session = AttendanceSession.objects.create(
            offering=self.other_offering,
            date=date(2026, 7, 14),
            taken_by=other_teacher,
        )

    def test_campus_admin_attendance_list_ignores_other_campus_filter(self):
        self.client.login(username="attendance_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_attendance_sessions_list"), {"campus": self.other_campus.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teacher Visible")
        self.assertNotContains(response, "Teacher Hidden")

    def test_campus_admin_cannot_access_other_campus_attendance_session(self):
        self.client.login(username="attendance_campus_admin", password="test-pass-123")

        get_response = self.client.get(reverse("admin_attendance_session_detail", kwargs={"pk": self.hidden_session.pk}))
        post_response = self.client.post(
            reverse("admin_attendance_session_detail", kwargs={"pk": self.hidden_session.pk}),
            {"action": "sync_students"},
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
