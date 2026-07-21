from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile

from .models import Activity, ActivityMember
from .programme_models import (
    ActivityAchievement,
    ActivityAttendance,
    ActivityGroup,
    ActivityParticipation,
    ActivityProgramme,
    ActivitySession,
)
from .programme_services import (
    activity_programme_readiness,
    bootstrap_activity_programmes,
    complete_activity_session,
    learner_co_curricular_summary,
    populate_session_attendance,
    update_attendance_entry,
)


class Phase8CoCurricularTests(TestCase):
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
            student_id="P8-001",
            first_name="Amina",
            last_name="Player",
        )
        self.student_two = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P8-002",
            first_name="Daniel",
            last_name="Member",
        )
        self.activity = Activity.objects.create(
            name="Football",
            type=Activity.SPORT,
            campus=self.campus,
        )
        self.other_activity = Activity.objects.create(
            name="Debate Club",
            type=Activity.CLUB,
            campus=self.campus,
        )
        self.membership = ActivityMember.objects.create(
            activity=self.activity,
            student=self.student,
        )
        self.other_membership = ActivityMember.objects.create(
            activity=self.other_activity,
            student=self.student_two,
        )
        self.user = get_user_model().objects.create_superuser(
            username="phase8admin",
            email="phase8@example.com",
            password="test-password",
        )

    def test_bootstrap_is_dry_run_first_safe_and_idempotent(self):
        preview = bootstrap_activity_programmes(dry_run=True)
        self.assertEqual(preview["programme_created_count"], 2)
        self.assertEqual(preview["participation_created_count"], 2)
        self.assertEqual(ActivityProgramme.objects.count(), 0)
        self.assertEqual(ActivityParticipation.objects.count(), 0)

        first = bootstrap_activity_programmes(dry_run=False)
        second = bootstrap_activity_programmes(dry_run=False)

        self.assertEqual(first["programme_created_count"], 2)
        self.assertEqual(second["programme_created_count"], 0)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(ActivityMember.objects.count(), 2)
        football = ActivityProgramme.objects.get(activity=self.activity)
        self.assertEqual(football.participation_mode, ActivityProgramme.TEAM)
        self.assertTrue(football.competitive)

    def test_session_roster_uses_existing_memberships_and_never_assumes_presence(self):
        bootstrap_activity_programmes(dry_run=False)
        session = ActivitySession.objects.create(
            activity=self.activity,
            title="Training",
            session_type=ActivitySession.TRAINING,
            starts_at=timezone.now(),
            created_by=self.user,
        )
        summary = populate_session_attendance(session, dry_run=False)
        entry = session.attendance_entries.get()

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(entry.membership, self.membership)
        self.assertEqual(entry.status, ActivityAttendance.UNMARKED)
        self.assertEqual(ActivityMember.objects.count(), 2)

    def test_group_session_includes_only_assigned_active_members(self):
        bootstrap_activity_programmes(dry_run=False)
        programme = ActivityProgramme.objects.get(activity=self.activity)
        group = ActivityGroup.objects.create(programme=programme, name="First Team")
        participation = self.membership.participation_profile
        participation.group = group
        participation.save()
        second = ActivityMember.objects.create(activity=self.activity, student=self.student_two)
        ActivityParticipation.objects.create(membership=second)
        session = ActivitySession.objects.create(
            activity=self.activity,
            group=group,
            title="First team practice",
            starts_at=timezone.now(),
        )

        populate_session_attendance(session, dry_run=False)

        self.assertEqual(session.attendance_entries.count(), 1)
        self.assertEqual(session.attendance_entries.get().membership, self.membership)

    def test_session_completion_requires_deliberate_attendance(self):
        bootstrap_activity_programmes(dry_run=False)
        session = ActivitySession.objects.create(
            activity=self.activity,
            title="Match",
            session_type=ActivitySession.MATCH,
            starts_at=timezone.now(),
        )
        populate_session_attendance(session, dry_run=False)
        with self.assertRaises(ValidationError):
            complete_activity_session(session)

        entry = session.attendance_entries.get()
        update_attendance_entry(entry, status=ActivityAttendance.PRESENT, user=self.user)
        complete_activity_session(session)
        session.refresh_from_db()

        self.assertEqual(session.status, ActivitySession.COMPLETED)
        self.assertEqual(entry.membership, self.membership)

    def test_participation_rejects_group_from_another_activity(self):
        bootstrap_activity_programmes(dry_run=False)
        other_programme = ActivityProgramme.objects.get(activity=self.other_activity)
        other_group = ActivityGroup.objects.create(programme=other_programme, name="Debaters")
        participation = self.membership.participation_profile
        participation.group = other_group
        with self.assertRaises(ValidationError):
            participation.full_clean()

    def test_achievement_reuses_membership_without_changing_membership(self):
        bootstrap_activity_programmes(dry_run=False)
        achievement = ActivityAchievement.objects.create(
            membership=self.membership,
            title="District champions",
            achievement_type=ActivityAchievement.AWARD,
            level=ActivityAchievement.DISTRICT,
            recorded_by=self.user,
        )
        summary = learner_co_curricular_summary(self.student)

        self.assertEqual(achievement.membership, self.membership)
        self.assertEqual(summary["achievement_count"], 1)
        self.assertTrue(ActivityMember.objects.get(pk=self.membership.pk).is_active)

    def test_readiness_reports_clearance_and_capacity_alerts_without_rewriting_data(self):
        bootstrap_activity_programmes(dry_run=False)
        programme = ActivityProgramme.objects.get(activity=self.activity)
        programme.capacity = 0
        programme.guardian_consent_required = True
        programme.medical_clearance_required = True
        programme.save()
        participation = self.membership.participation_profile
        participation.guardian_consent_status = ActivityParticipation.PENDING
        participation.medical_clearance_status = ActivityParticipation.PENDING
        participation.save()

        readiness = activity_programme_readiness()

        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["over_capacity_count"], 1)
        self.assertEqual(readiness["consent_missing_count"], 1)
        self.assertEqual(readiness["medical_clearance_missing_count"], 1)
        self.assertEqual(ActivityMember.objects.count(), 2)
