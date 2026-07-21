from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, UserRole

from .hardening_models import GuardianContactLog, WelfareCaseEscalation
from .hardening_services import (
    confirmed_guardian_contact_for_leave,
    escalate_welfare_case,
    phase7_operational_readiness,
    reconcile_roll_call_leave_statuses,
    record_guardian_contact,
    student_boarding_readiness,
)
from .models import (
    Bed,
    BedAllocation,
    BoardingLeave,
    BoardingProfile,
    Hostel,
    HostelRollCall,
    HostelRollCallEntry,
    HostelRoom,
    WelfareCase,
    WelfareCaseAction,
)


class Phase7OperationalHardeningTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        if not self.campus:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                is_default=True,
                is_active=True,
            )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P7H-001",
            first_name="Amina",
            last_name="Boarder",
        )
        self.other_student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P7H-002",
            first_name="Brian",
            last_name="Other",
        )
        self.hostel = Hostel.objects.create(name="Safety House", code="SH")
        room = HostelRoom.objects.create(hostel=self.hostel, name="Room 1", capacity=2)
        self.bed = Bed.objects.create(room=room, label="A")
        self.allocation = BedAllocation.objects.create(
            bed=self.bed,
            student=self.student,
            status=BedAllocation.ACTIVE,
        )
        self.profile = BoardingProfile.objects.create(
            student=self.student,
            boarding_status=BoardingProfile.BOARDER,
            primary_guardian_name="Parent One",
            primary_guardian_phone="0700000000",
            authorised_pickup_people=["Parent One"],
        )
        self.user = get_user_model().objects.create_superuser(
            username="phase7hardening",
            email="phase7hardening@example.com",
            password="test-password",
        )
        self.now = timezone.now()
        self.leave = BoardingLeave.objects.create(
            student=self.student,
            bed_allocation=self.allocation,
            expected_departure_at=self.now - timedelta(hours=1),
            expected_return_at=self.now + timedelta(days=1),
            guardian_name="Parent One",
            guardian_phone="0700000000",
            status=BoardingLeave.DEPARTED,
            departed_at=self.now - timedelta(hours=1),
        )

    def test_guardian_contact_confirmation_is_auditable_and_preserves_sources(self):
        log = record_guardian_contact(
            student=self.student,
            boarding_leave=self.leave,
            purpose=GuardianContactLog.LEAVE_APPROVAL,
            method=GuardianContactLog.PHONE,
            outcome=GuardianContactLog.CONFIRMED,
            contact_name="Parent One",
            contact_phone="0700000000",
            note="Confirmed collection.",
            recorded_by=self.user,
        )

        self.assertEqual(confirmed_guardian_contact_for_leave(self.leave), log)
        self.assertEqual(BedAllocation.objects.get(pk=self.allocation.pk).status, BedAllocation.ACTIVE)
        self.assertEqual(BoardingLeave.objects.get(pk=self.leave.pk).status, BoardingLeave.DEPARTED)

    def test_contact_log_rejects_a_link_from_another_learner(self):
        with self.assertRaises(ValidationError):
            record_guardian_contact(
                student=self.other_student,
                boarding_leave=self.leave,
                purpose=GuardianContactLog.LEAVE_APPROVAL,
                method=GuardianContactLog.PHONE,
                outcome=GuardianContactLog.CONFIRMED,
                contact_name="Parent",
            )

    def test_roll_call_reconciliation_is_dry_run_first_and_preserves_explicit_decisions(self):
        roll_call = HostelRollCall.objects.create(
            hostel=self.hostel,
            taken_at=self.now,
            recorded_by=self.user,
        )
        entry = HostelRollCallEntry.objects.create(
            roll_call=roll_call,
            student=self.student,
            bed_allocation=self.allocation,
            presence=HostelRollCallEntry.UNMARKED,
        )

        preview = reconcile_roll_call_leave_statuses(roll_call, dry_run=True)
        entry.refresh_from_db()
        self.assertEqual(preview["set_on_leave_count"], 1)
        self.assertEqual(entry.presence, HostelRollCallEntry.UNMARKED)

        applied = reconcile_roll_call_leave_statuses(roll_call, dry_run=False)
        entry.refresh_from_db()
        self.assertEqual(applied["set_on_leave_count"], 1)
        self.assertEqual(entry.presence, HostelRollCallEntry.ON_LEAVE)
        self.assertEqual(entry.boarding_leave, self.leave)

        entry.presence = HostelRollCallEntry.ABSENT
        entry.save(update_fields=["presence"])
        preserved = reconcile_roll_call_leave_statuses(roll_call, dry_run=False)
        entry.refresh_from_db()
        self.assertEqual(preserved["preserved_explicit_count"], 1)
        self.assertEqual(entry.presence, HostelRollCallEntry.ABSENT)

    def test_stale_on_leave_entry_returns_to_unmarked(self):
        roll_call = HostelRollCall.objects.create(hostel=self.hostel, taken_at=self.now)
        entry = HostelRollCallEntry.objects.create(
            roll_call=roll_call,
            student=self.student,
            bed_allocation=self.allocation,
            boarding_leave=self.leave,
            presence=HostelRollCallEntry.ON_LEAVE,
        )
        self.leave.status = BoardingLeave.RETURNED
        self.leave.returned_at = self.now
        self.leave.save(update_fields=["status", "returned_at", "updated_at"])

        summary = reconcile_roll_call_leave_statuses(roll_call, dry_run=False)
        entry.refresh_from_db()

        self.assertEqual(summary["reset_to_unmarked_count"], 1)
        self.assertEqual(entry.presence, HostelRollCallEntry.UNMARKED)
        self.assertIsNone(entry.boarding_leave)

    def test_escalation_creates_auditable_action_and_response_deadline(self):
        case = WelfareCase.objects.create(
            student=self.student,
            title="Urgent boarding concern",
            severity=WelfareCase.HIGH,
            opened_by=self.user,
        )
        due = self.now + timedelta(hours=2)

        escalation = escalate_welfare_case(
            case,
            level=WelfareCaseEscalation.SENIOR,
            reason="Senior review is required.",
            user=self.user,
            response_due_at=due,
            guardian_contact_required=True,
        )
        case.refresh_from_db()

        self.assertEqual(escalation.level, WelfareCaseEscalation.SENIOR)
        self.assertEqual(escalation.response_due_at, due)
        self.assertTrue(escalation.guardian_contact_required)
        self.assertEqual(case.status, WelfareCase.MONITORING)
        self.assertTrue(
            WelfareCaseAction.objects.filter(
                welfare_case=case,
                action_type=WelfareCaseAction.ESCALATION,
            ).exists()
        )

    def test_readiness_surfaces_contact_and_response_risks(self):
        self.profile.primary_guardian_phone = ""
        self.profile.save(update_fields=["primary_guardian_phone", "updated_at"])
        case = WelfareCase.objects.create(
            student=self.student,
            title="Overdue response",
            severity=WelfareCase.CRITICAL,
        )
        WelfareCaseEscalation.objects.create(
            welfare_case=case,
            level=WelfareCaseEscalation.EMERGENCY,
            reason="Immediate review.",
            response_due_at=self.now - timedelta(minutes=10),
        )

        learner = student_boarding_readiness(self.student)
        readiness = phase7_operational_readiness()

        self.assertFalse(learner["ready"])
        self.assertEqual(readiness["boarder_missing_guardian_contact_count"], 1)
        self.assertEqual(readiness["departed_without_confirmation_count"], 1)
        self.assertEqual(readiness["overdue_case_response_count"], 1)
        self.assertFalse(readiness["ready"])


class Phase7OperationalHardeningViewTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        if not self.campus:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                is_default=True,
                is_active=True,
            )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P7H-VIEW",
            first_name="View",
            last_name="Learner",
        )
        self.hostel = Hostel.objects.create(name="View House", code="VH2")
        room = HostelRoom.objects.create(hostel=self.hostel, name="Room 1", capacity=1)
        bed = Bed.objects.create(room=room, label="A")
        self.allocation = BedAllocation.objects.create(bed=bed, student=self.student)
        BoardingProfile.objects.create(
            student=self.student,
            boarding_status=BoardingProfile.BOARDER,
            primary_guardian_name="Guardian",
            primary_guardian_phone="0711111111",
        )
        self.user = get_user_model().objects.create_superuser(
            username="phase7hardeningview",
            email="phase7hardeningview@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)
        now = timezone.now()
        self.leave = BoardingLeave.objects.create(
            student=self.student,
            bed_allocation=self.allocation,
            expected_departure_at=now - timedelta(hours=1),
            expected_return_at=now + timedelta(days=1),
            guardian_name="Guardian",
            guardian_phone="0711111111",
            status=BoardingLeave.DEPARTED,
        )
        self.case = WelfareCase.objects.create(
            student=self.student,
            title="View welfare case",
            opened_by=self.user,
        )

    def test_full_administrator_can_open_hardening_dashboard(self):
        response = self.client.get(reverse("admin_boarding_welfare_hardening"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational safety and evidence")

    def test_leave_contact_view_records_evidence(self):
        response = self.client.post(
            reverse("admin_boarding_leave_contact", args=[self.leave.pk]),
            {
                "purpose": GuardianContactLog.LEAVE_APPROVAL,
                "method": GuardianContactLog.PHONE,
                "outcome": GuardianContactLog.CONFIRMED,
                "contact_name": "Guardian",
                "contact_phone": "0711111111",
                "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "note": "Confirmed.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GuardianContactLog.objects.filter(
                boarding_leave=self.leave,
                outcome=GuardianContactLog.CONFIRMED,
            ).exists()
        )

    def test_case_escalation_view_records_deadline(self):
        response = self.client.post(
            reverse("admin_welfare_case_escalate", args=[self.case.pk]),
            {
                "level": WelfareCaseEscalation.SENIOR,
                "response_due_at": (timezone.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
                "reason": "Senior review.",
                "guardian_contact_required": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        escalation = WelfareCaseEscalation.objects.get(welfare_case=self.case)
        self.assertEqual(escalation.level, WelfareCaseEscalation.SENIOR)
        self.assertTrue(escalation.guardian_contact_required)

    def test_campus_administrator_cannot_open_institution_hardening_dashboard(self):
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        campus_user = get_user_model().objects.create_user(
            username="phase7hardeningcampus",
            password="test-password",
        )
        UserRole.objects.create(user=campus_user, role=role, campus=self.campus)
        self.client.force_login(campus_user)

        response = self.client.get(reverse("admin_boarding_welfare_hardening"))

        self.assertEqual(response.status_code, 403)
