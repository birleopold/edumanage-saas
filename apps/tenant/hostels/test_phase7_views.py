from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, UserRole

from .models import (
    Bed,
    BedAllocation,
    BoardingLeave,
    BoardingProfile,
    Hostel,
    HostelRoom,
    WelfareCase,
)


class Phase7WelfareViewTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Phase 7 School")
        self.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P7-VIEW",
            first_name="Amina",
            last_name="Learner",
        )
        self.hostel = Hostel.objects.create(name="Victoria House", code="VH")
        room = HostelRoom.objects.create(hostel=self.hostel, name="Room 1", capacity=1)
        bed = Bed.objects.create(room=room, label="A")
        self.allocation = BedAllocation.objects.create(bed=bed, student=self.student)
        self.superuser = get_user_model().objects.create_superuser(
            username="phase7super",
            email="phase7super@example.com",
            password="test-password",
        )
        self.client.force_login(self.superuser)

    def test_full_administrator_can_open_dashboard_and_bootstrap_profiles(self):
        response = self.client.get(reverse("admin_boarding_welfare_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Boarding and welfare coordination")

        response = self.client.post(
            reverse("admin_boarding_welfare_dashboard"),
            {"action": "bootstrap_profiles"},
        )
        self.assertEqual(response.status_code, 302)
        profile = BoardingProfile.objects.get(student=self.student)
        self.assertEqual(profile.boarding_status, BoardingProfile.BOARDER)
        self.assertEqual(BedAllocation.objects.count(), 1)

    def test_roll_call_create_uses_current_allocation_without_changing_it(self):
        now = timezone.now()
        response = self.client.post(
            reverse("admin_hostel_roll_call_create"),
            {
                "hostel": self.hostel.pk,
                "roll_call_date": now.date().isoformat(),
                "shift": "EVENING",
                "taken_at": now.strftime("%Y-%m-%dT%H:%M"),
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BedAllocation.objects.count(), 1)
        self.assertEqual(self.student.hostel_roll_call_entries.count(), 1)

    def test_leave_transition_view_records_approval_departure_and_return(self):
        now = timezone.now()
        leave = BoardingLeave.objects.create(
            student=self.student,
            bed_allocation=self.allocation,
            expected_departure_at=now + timedelta(hours=1),
            expected_return_at=now + timedelta(days=1),
        )
        self.client.post(reverse("admin_boarding_leave_transition", args=[leave.pk, "approve"]))
        self.client.post(
            reverse("admin_boarding_leave_transition", args=[leave.pk, "depart"]),
            {"handover_to": "Guardian"},
        )
        self.client.post(
            reverse("admin_boarding_leave_transition", args=[leave.pk, "return"]),
            {"return_note": "Safe return"},
        )
        leave.refresh_from_db()
        self.assertEqual(leave.status, BoardingLeave.RETURNED)
        self.assertEqual(BedAllocation.objects.get(pk=self.allocation.pk).status, BedAllocation.ACTIVE)

    def test_campus_administrator_can_use_operations_but_not_global_readiness(self):
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        user = get_user_model().objects.create_user(
            username="phase7campus",
            password="test-password",
        )
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("admin_boarding_welfare_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_boarding_leaves")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin_hostel_roll_calls")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin_welfare_cases")).status_code, 200)

    def test_confidential_case_is_hidden_from_unassigned_campus_administrator(self):
        case = WelfareCase.objects.create(
            student=self.student,
            title="Sensitive support",
            confidential=True,
            opened_by=self.superuser,
        )
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        user = get_user_model().objects.create_user(
            username="phase7restricted",
            password="test-password",
        )
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        response = self.client.get(reverse("admin_welfare_case_detail", args=[case.pk]))
        self.assertEqual(response.status_code, 404)
