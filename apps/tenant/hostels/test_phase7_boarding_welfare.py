from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.tenant.discipline.models import Incident
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.sickbay.models import SickbayVisit
from apps.tenant.students.models import StudentProfile

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
)
from .welfare_services import (
    approve_leave,
    boarding_welfare_readiness,
    bootstrap_boarding_profiles,
    complete_roll_call,
    populate_roll_call,
    record_departure,
    record_return,
    student_welfare_timeline,
)


class Phase7BoardingWelfareTests(TestCase):
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
            student_id="P7-001",
            first_name="Amina",
            last_name="Boarder",
        )
        self.day_student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P7-002",
            first_name="Daniel",
            last_name="Day",
        )
        self.hostel = Hostel.objects.create(name="Nile House", code="NH")
        self.room = HostelRoom.objects.create(hostel=self.hostel, name="Room 1", capacity=2)
        self.bed = Bed.objects.create(room=self.room, label="A")
        self.allocation = BedAllocation.objects.create(
            bed=self.bed,
            student=self.student,
            status=BedAllocation.ACTIVE,
        )
        self.user = get_user_model().objects.create_superuser(
            username="phase7admin",
            email="phase7@example.com",
            password="test-password",
        )

    def test_profile_bootstrap_is_safe_and_idempotent(self):
        dry_run = bootstrap_boarding_profiles(dry_run=True)
        self.assertEqual(dry_run["created_count"], 2)
        self.assertEqual(BoardingProfile.objects.count(), 0)

        first = bootstrap_boarding_profiles(dry_run=False)
        second = bootstrap_boarding_profiles(dry_run=False)

        self.assertEqual(first["created_count"], 2)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(BoardingProfile.objects.get(student=self.student).boarding_status, BoardingProfile.BOARDER)
        self.assertEqual(BoardingProfile.objects.get(student=self.day_student).boarding_status, BoardingProfile.DAY)
        self.assertEqual(BedAllocation.objects.count(), 1)
        self.assertEqual(BedAllocation.objects.get(), self.allocation)

    def test_profile_current_allocation_reuses_existing_record(self):
        profile = BoardingProfile.objects.create(
            student=self.student,
            boarding_status=BoardingProfile.BOARDER,
        )
        self.assertEqual(profile.current_allocation, self.allocation)

    def test_roll_call_population_never_assumes_presence(self):
        roll_call = HostelRollCall.objects.create(
            hostel=self.hostel,
            recorded_by=self.user,
        )
        summary = populate_roll_call(roll_call, dry_run=False)
        entry = HostelRollCallEntry.objects.get(roll_call=roll_call, student=self.student)

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(entry.presence, HostelRollCallEntry.UNMARKED)
        self.assertEqual(entry.bed_allocation, self.allocation)

    def test_departed_approved_leave_is_linked_to_roll_call(self):
        now = timezone.now()
        leave = BoardingLeave.objects.create(
            student=self.student,
            bed_allocation=self.allocation,
            leave_type=BoardingLeave.HOME,
            expected_departure_at=now - timedelta(hours=1),
            expected_return_at=now + timedelta(days=1),
            status=BoardingLeave.DEPARTED,
            departed_at=now - timedelta(hours=1),
        )
        roll_call = HostelRollCall.objects.create(hostel=self.hostel, taken_at=now)

        populate_roll_call(roll_call, dry_run=False)
        entry = roll_call.entries.get(student=self.student)

        self.assertEqual(entry.presence, HostelRollCallEntry.ON_LEAVE)
        self.assertEqual(entry.boarding_leave, leave)

    def test_roll_call_cannot_complete_with_unmarked_learners(self):
        roll_call = HostelRollCall.objects.create(hostel=self.hostel)
        populate_roll_call(roll_call, dry_run=False)
        with self.assertRaises(ValidationError):
            complete_roll_call(roll_call)

        entry = roll_call.entries.get()
        entry.presence = HostelRollCallEntry.PRESENT
        entry.save()
        complete_roll_call(roll_call)
        roll_call.refresh_from_db()
        self.assertEqual(roll_call.status, HostelRollCall.COMPLETED)

    def test_leave_workflow_requires_explicit_transitions(self):
        now = timezone.now()
        leave = BoardingLeave.objects.create(
            student=self.student,
            bed_allocation=self.allocation,
            leave_type=BoardingLeave.HOME,
            expected_departure_at=now + timedelta(hours=1),
            expected_return_at=now + timedelta(days=2),
        )

        approve_leave(leave, self.user)
        record_departure(leave, self.user, handover_to="Parent")
        record_return(leave, self.user, note="Returned safely")
        leave.refresh_from_db()

        self.assertEqual(leave.status, BoardingLeave.RETURNED)
        self.assertEqual(leave.handover_to, "Parent")
        self.assertEqual(leave.return_note, "Returned safely")
        self.assertEqual(BedAllocation.objects.get(pk=self.allocation.pk).status, BedAllocation.ACTIVE)

    def test_welfare_links_reference_existing_sources_without_copying(self):
        visit = SickbayVisit.objects.create(
            student=self.student,
            complaint="Headache",
            severity=SickbayVisit.MILD,
        )
        incident = Incident.objects.create(
            student=self.student,
            title="Late return",
            severity=Incident.LOW,
        )
        case = WelfareCase.objects.create(
            student=self.student,
            category=WelfareCase.BOARDING,
            title="Monitor learner",
            linked_sickbay_visit=visit,
            linked_discipline_incident=incident,
            linked_bed_allocation=self.allocation,
        )

        self.assertEqual(case.linked_sickbay_visit, visit)
        self.assertEqual(case.linked_discipline_incident, incident)
        self.assertEqual(case.linked_bed_allocation, self.allocation)
        self.assertEqual(SickbayVisit.objects.count(), 1)
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(BedAllocation.objects.count(), 1)

    def test_student_timeline_combines_existing_sources(self):
        BoardingProfile.objects.create(student=self.student, boarding_status=BoardingProfile.BOARDER)
        SickbayVisit.objects.create(student=self.student, complaint="Flu")
        Incident.objects.create(student=self.student, title="Uniform concern")
        WelfareCase.objects.create(student=self.student, title="Follow-up")

        timeline = student_welfare_timeline(self.student)
        kinds = {item.kind for item in timeline}

        self.assertTrue({"BOARDING", "HEALTH", "DISCIPLINE", "WELFARE"}.issubset(kinds))

    def test_readiness_accepts_aligned_profiles_and_allocations(self):
        bootstrap_boarding_profiles(dry_run=False)
        readiness = boarding_welfare_readiness()
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["missing_profile_count"], 0)
        self.assertEqual(readiness["allocation_without_boarder_profile_count"], 0)
