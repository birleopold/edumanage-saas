from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import RouteStop, StudentTransportAssignment, TransportRoute, Vehicle


class TransportAssignmentCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Transport Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Transport",
            student_id="TR-VISIBLE",
            campus=self.campus,
            is_active=True,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Transport",
            student_id="TR-HIDDEN",
            campus=self.other_campus,
            is_active=True,
        )
        self.vehicle = Vehicle.objects.create(
            name="Main Bus",
            vehicle_type=Vehicle.BUS,
            plate_number="TR-001",
            capacity=40,
            status=Vehicle.OPERATIONAL,
            is_active=True,
        )
        self.route = TransportRoute.objects.create(
            name="Main Route",
            code="TR-MAIN",
            vehicle=self.vehicle,
            shift=TransportRoute.BOTH,
            is_active=True,
        )
        self.stop = RouteStop.objects.create(
            route=self.route,
            name="Main Stop",
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
        self.hidden_assignment = StudentTransportAssignment.objects.create(
            student=self.hidden_student,
            route=self.route,
            stop=self.stop,
            service_type=StudentTransportAssignment.BOTH,
            start_date=date(2026, 1, 1),
            is_active=True,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="transport_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_assignment_list_sees_own_students_only(self):
        self.client.login(username="transport_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_transport_assignments_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TR-VISIBLE")
        self.assertNotContains(response, "TR-HIDDEN")

    def test_campus_admin_cannot_access_other_campus_assignment_detail_or_edit(self):
        self.client.login(username="transport_campus_admin", password="test-pass-123")

        detail_response = self.client.get(reverse("admin_transport_assignment_detail", kwargs={"pk": self.hidden_assignment.pk}))
        edit_response = self.client.get(reverse("admin_transport_assignment_edit", kwargs={"pk": self.hidden_assignment.pk}))

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)

    def test_campus_admin_cannot_create_assignment_for_other_campus_student(self):
        self.hidden_assignment.delete()
        self.client.login(username="transport_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_transport_assignment_create"),
            {
                "student": self.hidden_student.pk,
                "route": self.route.pk,
                "stop": self.stop.pk,
                "service_type": StudentTransportAssignment.BOTH,
                "start_date": "2026-02-01",
                "end_date": "",
                "monthly_fee": "",
                "emergency_contact": "",
                "emergency_phone": "",
                "special_needs": "",
                "notes": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            StudentTransportAssignment.objects.filter(
                student=self.hidden_student,
                start_date=date(2026, 2, 1),
            ).exists()
        )

    def test_campus_admin_cannot_move_assignment_to_other_campus_student(self):
        self.hidden_assignment.delete()
        self.client.login(username="transport_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_transport_assignment_edit", kwargs={"pk": self.assignment.pk}),
            {
                "student": self.hidden_student.pk,
                "route": self.route.pk,
                "stop": self.stop.pk,
                "service_type": self.assignment.service_type,
                "start_date": "2026-01-01",
                "end_date": "",
                "monthly_fee": "",
                "emergency_contact": "",
                "emergency_phone": "",
                "special_needs": "",
                "notes": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.student, self.student)
