from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import ParentNotification, RouteStop, StudentTransportAssignment, TransportRoute, Vehicle


class TransportNoticeAndPortalAccessTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        self.other_campus = Campus.objects.create(
            organization=organization,
            name="Other Transport Campus",
            is_active=True,
        )

        self.student_role, _ = Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        self.parent_role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
        self.campus_admin_role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )

        self.student_user = User.objects.create_user(username="transport_student", password="test-pass-123")
        self.student_user.roles.add(self.student_role)
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            first_name="Visible",
            last_name="Student",
            student_id="TR-STUDENT-1",
            campus=self.campus,
            is_active=True,
        )

        self.other_student_user = User.objects.create_user(username="other_transport_student", password="test-pass-123")
        self.other_student_user.roles.add(self.student_role)
        self.other_student = StudentProfile.objects.create(
            user=self.other_student_user,
            first_name="Other",
            last_name="Student",
            student_id="TR-STUDENT-2",
            campus=self.other_campus,
            is_active=True,
        )

        self.parent_user = User.objects.create_user(username="transport_parent", password="test-pass-123")
        self.parent_user.roles.add(self.parent_role)
        self.parent = ParentProfile.objects.create(
            user=self.parent_user,
            first_name="Transport",
            last_name="Parent",
            is_active=True,
        )
        ParentStudentLink.objects.create(parent=self.parent, student=self.student, is_primary=True)

        self.vehicle = Vehicle.objects.create(
            name="Transport Bus",
            vehicle_type=Vehicle.BUS,
            plate_number="TR-NOTICE-001",
            capacity=40,
            status=Vehicle.OPERATIONAL,
            is_active=True,
        )
        self.route = TransportRoute.objects.create(
            name="Transport Route",
            code="TR-NOTICE",
            vehicle=self.vehicle,
            shift=TransportRoute.BOTH,
            is_active=True,
        )
        self.stop = RouteStop.objects.create(
            route=self.route,
            name="Transport Stop",
            order=1,
            is_active=True,
        )
        self.assignment = StudentTransportAssignment.objects.create(
            student=self.student,
            route=self.route,
            stop=self.stop,
            service_type=StudentTransportAssignment.BOTH,
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        self.other_assignment = StudentTransportAssignment.objects.create(
            student=self.other_student,
            route=self.route,
            stop=self.stop,
            service_type=StudentTransportAssignment.BOTH,
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        self.campus_admin = User.objects.create_user(username="transport_notice_admin", password="test-pass-123")
        self.campus_admin.roles.add(self.campus_admin_role)
        UserRole.objects.create(user=self.campus_admin, role=self.campus_admin_role, campus=self.campus)

    def test_parent_can_open_linked_assignment_only(self):
        self.client.login(username="transport_parent", password="test-pass-123")

        allowed = self.client.get(
            reverse("parent_transport_assignment_detail", kwargs={"pk": self.assignment.pk})
        )
        denied = self.client.get(
            reverse("parent_transport_assignment_detail", kwargs={"pk": self.other_assignment.pk})
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 404)

    def test_student_can_open_own_assignment_only(self):
        self.client.login(username="transport_student", password="test-pass-123")

        allowed = self.client.get(
            reverse("student_transport_assignment_detail", kwargs={"pk": self.assignment.pk})
        )
        denied = self.client.get(
            reverse("student_transport_assignment_detail", kwargs={"pk": self.other_assignment.pk})
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 404)

    def test_campus_admin_notice_list_is_campus_scoped(self):
        ParentNotification.objects.create(
            assignment=self.assignment,
            notification_type=ParentNotification.DELAY,
            message="Visible campus notice",
        )
        ParentNotification.objects.create(
            assignment=self.other_assignment,
            notification_type=ParentNotification.DELAY,
            message="Hidden campus notice",
        )
        self.client.login(username="transport_notice_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_transport_notices_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible campus notice")
        self.assertNotContains(response, "Hidden campus notice")

    def test_campus_admin_without_scope_sees_no_notices(self):
        ParentNotification.objects.create(
            assignment=self.assignment,
            notification_type=ParentNotification.DELAY,
            message="Must remain hidden",
        )
        unscoped_admin = User.objects.create_user(
            username="unscoped_transport_admin",
            password="test-pass-123",
        )
        unscoped_admin.roles.add(self.campus_admin_role)
        self.client.login(username="unscoped_transport_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_transport_notices_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Must remain hidden")

    def test_campus_admin_cannot_create_notice_for_another_campus(self):
        self.client.login(username="transport_notice_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_transport_notice_create"),
            {
                "assignment": self.other_assignment.pk,
                "notification_type": ParentNotification.GENERAL,
                "message": "Must not be created",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ParentNotification.objects.filter(message="Must not be created").exists())

    def test_campus_admin_can_create_notice_for_own_campus(self):
        self.client.login(username="transport_notice_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_transport_notice_create"),
            {
                "assignment": self.assignment.pk,
                "notification_type": ParentNotification.GENERAL,
                "message": "Campus transport update",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ParentNotification.objects.filter(message="Campus transport update").exists())
