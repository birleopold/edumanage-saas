from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .integrity import audit_transport_integrity
from .models import RouteStop, StudentTransportAssignment, TransportRoute, Vehicle, VehicleTracking


class TransportIntegrityAuditTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        self.student_one = StudentProfile.objects.create(
            first_name="Audit",
            last_name="One",
            student_id="TR-AUDIT-1",
            campus=self.campus,
            is_active=True,
        )
        self.student_two = StudentProfile.objects.create(
            first_name="Audit",
            last_name="Two",
            student_id="TR-AUDIT-2",
            campus=self.campus,
            is_active=True,
        )
        self.vehicle_one = Vehicle.objects.create(
            name="Audit Bus One",
            vehicle_type=Vehicle.BUS,
            plate_number="TR-AUDIT-V1",
            capacity=1,
            status=Vehicle.OPERATIONAL,
            is_active=True,
        )
        self.vehicle_two = Vehicle.objects.create(
            name="Audit Bus Two",
            vehicle_type=Vehicle.BUS,
            plate_number="TR-AUDIT-V2",
            capacity=10,
            status=Vehicle.OPERATIONAL,
            is_active=True,
        )
        self.route_one = TransportRoute.objects.create(
            name="Audit Route One",
            code="TR-AUDIT-R1",
            vehicle=self.vehicle_one,
            shift=TransportRoute.BOTH,
            is_active=True,
        )
        self.route_two = TransportRoute.objects.create(
            name="Audit Route Two",
            code="TR-AUDIT-R2",
            vehicle=self.vehicle_two,
            shift=TransportRoute.BOTH,
            is_active=False,
        )
        self.stop_one = RouteStop.objects.create(
            route=self.route_one,
            name="Audit Stop One",
            order=1,
            is_active=True,
        )
        self.stop_two = RouteStop.objects.create(
            route=self.route_two,
            name="Audit Stop Two",
            order=1,
            is_active=False,
        )

    def test_audit_detects_transport_conflicts(self):
        StudentTransportAssignment.objects.create(
            student=self.student_one,
            route=self.route_one,
            stop=self.stop_two,
            service_type=StudentTransportAssignment.BOTH,
            start_date=date(2026, 1, 1),
            end_date=timezone.localdate() - timedelta(days=1),
            is_active=True,
        )
        StudentTransportAssignment.objects.create(
            student=self.student_one,
            route=self.route_two,
            stop=self.stop_two,
            service_type=StudentTransportAssignment.BOTH,
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        StudentTransportAssignment.objects.create(
            student=self.student_two,
            route=self.route_one,
            stop=self.stop_one,
            service_type=StudentTransportAssignment.BOTH,
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        VehicleTracking.objects.create(
            vehicle=self.vehicle_two,
            route=self.route_one,
            latitude="0.347596",
            longitude="32.582520",
            is_moving=True,
        )

        codes = {issue.code for issue in audit_transport_integrity()}

        self.assertIn("MULTIPLE_ACTIVE_TRANSPORT_ASSIGNMENTS", codes)
        self.assertIn("TRANSPORT_STOP_ROUTE_MISMATCH", codes)
        self.assertIn("ACTIVE_ASSIGNMENT_INACTIVE_ROUTE", codes)
        self.assertIn("ACTIVE_ASSIGNMENT_INACTIVE_STOP", codes)
        self.assertIn("EXPIRED_ACTIVE_TRANSPORT_ASSIGNMENT", codes)
        self.assertIn("TRANSPORT_ROUTE_OVER_CAPACITY", codes)
        self.assertIn("TRACKING_ROUTE_VEHICLE_MISMATCH", codes)
