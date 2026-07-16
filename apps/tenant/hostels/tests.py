from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Bed, BedAllocation, Hostel, HostelRoom


class HostelAllocationCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Hostel Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Boarder",
            student_id="HOST-VISIBLE",
            campus=self.campus,
            is_active=True,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Boarder",
            student_id="HOST-HIDDEN",
            campus=self.other_campus,
            is_active=True,
        )
        self.hostel = Hostel.objects.create(name="Main Hostel", code="MH", is_active=True)
        self.room = HostelRoom.objects.create(hostel=self.hostel, name="Room One", code="R1", capacity=4, is_active=True)
        self.bed = Bed.objects.create(room=self.room, label="A", is_active=True)
        self.hidden_bed = Bed.objects.create(room=self.room, label="B", is_active=True)
        self.open_bed = Bed.objects.create(room=self.room, label="C", is_active=True)
        self.allocation = BedAllocation.objects.create(
            bed=self.bed,
            student=self.student,
            start_date=date(2026, 1, 1),
            status=BedAllocation.ACTIVE,
        )
        self.hidden_allocation = BedAllocation.objects.create(
            bed=self.hidden_bed,
            student=self.hidden_student,
            start_date=date(2026, 1, 1),
            status=BedAllocation.ACTIVE,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="hostel_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_allocation_list_sees_own_students_only(self):
        self.client.login(username="hostel_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_bed_allocations_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HOST-VISIBLE")
        self.assertNotContains(response, "HOST-HIDDEN")

    def test_campus_admin_cannot_edit_other_campus_allocation(self):
        self.client.login(username="hostel_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_bed_allocations_edit", kwargs={"pk": self.hidden_allocation.pk}))

        self.assertEqual(response.status_code, 404)

    def test_campus_admin_cannot_create_allocation_for_other_campus_student(self):
        self.hidden_allocation.delete()
        self.client.login(username="hostel_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_bed_allocations_create"),
            {
                "bed": self.hidden_bed.pk,
                "student": self.hidden_student.pk,
                "start_date": "2026-02-01",
                "end_date": "",
                "status": BedAllocation.ACTIVE,
                "note": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            BedAllocation.objects.filter(
                bed=self.hidden_bed,
                student=self.hidden_student,
                start_date=date(2026, 2, 1),
            ).exists()
        )

    def test_campus_admin_cannot_move_allocation_to_other_campus_student(self):
        self.hidden_allocation.delete()
        self.client.login(username="hostel_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_bed_allocations_edit", kwargs={"pk": self.allocation.pk}),
            {
                "bed": self.bed.pk,
                "student": self.hidden_student.pk,
                "start_date": "2026-01-01",
                "end_date": "",
                "status": BedAllocation.ACTIVE,
                "note": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.student, self.student)
