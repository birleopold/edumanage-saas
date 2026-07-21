from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, UserRole

from .models import Activity, ActivityMember
from .programme_models import ActivityAttendance, ActivityParticipation, ActivityProgramme, ActivitySession


class Phase8ProgrammeViewTests(TestCase):
    def setUp(self):
        organization = OrganizationProfile.objects.create(name="Phase 8 School")
        self.campus = Campus.objects.create(
            organization=organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="P8-VIEW",
            first_name="Amina",
            last_name="Learner",
        )
        self.activity = Activity.objects.create(
            name="Music Club",
            type=Activity.CO_CURRICULAR,
            campus=self.campus,
        )
        self.membership = ActivityMember.objects.create(
            activity=self.activity,
            student=self.student,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="phase8super",
            email="phase8super@example.com",
            password="test-password",
        )
        self.client.force_login(self.superuser)

    def test_full_administrator_can_open_dashboard_and_bootstrap_profiles(self):
        response = self.client.get(reverse("admin_activity_programme_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Co-curricular participation and achievement")

        response = self.client.post(
            reverse("admin_activity_programme_dashboard"),
            {"action": "bootstrap"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ActivityProgramme.objects.filter(activity=self.activity).exists())
        self.assertTrue(ActivityParticipation.objects.filter(membership=self.membership).exists())
        self.assertEqual(ActivityMember.objects.count(), 1)

    def test_session_create_builds_unmarked_roster_without_new_memberships(self):
        ActivityProgramme.objects.create(activity=self.activity, code="MUSIC")
        ActivityParticipation.objects.create(membership=self.membership)
        now = timezone.now()
        response = self.client.post(
            reverse("admin_activity_session_create"),
            {
                "activity": self.activity.pk,
                "group": "",
                "title": "Choir practice",
                "session_type": ActivitySession.PRACTICE,
                "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
                "ends_at": "",
                "location": "Music room",
                "attendance_required": "on",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        session = ActivitySession.objects.get()
        self.assertEqual(session.attendance_entries.count(), 1)
        self.assertEqual(session.attendance_entries.get().status, ActivityAttendance.UNMARKED)
        self.assertEqual(ActivityMember.objects.count(), 1)

    def test_participation_profile_can_be_updated_without_changing_membership(self):
        ActivityProgramme.objects.create(activity=self.activity, code="MUSIC")
        participation = ActivityParticipation.objects.create(membership=self.membership)
        response = self.client.post(
            reverse("admin_activity_participation_edit", args=[self.membership.pk]),
            {
                "group": "",
                "role": ActivityParticipation.LEADER,
                "guardian_consent_status": ActivityParticipation.APPROVED,
                "guardian_consent_recorded_at": "",
                "medical_clearance_status": ActivityParticipation.NOT_REQUIRED,
                "medical_clearance_recorded_at": "",
                "emergency_contact_name": "Parent",
                "emergency_contact_phone": "0700000000",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        participation.refresh_from_db()
        self.membership.refresh_from_db()
        self.assertEqual(participation.role, ActivityParticipation.LEADER)
        self.assertTrue(self.membership.is_active)

    def test_campus_administrator_can_use_operations_but_not_global_readiness(self):
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        user = get_user_model().objects.create_user(
            username="phase8campus",
            password="test-password",
        )
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("admin_activity_programme_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_activity_sessions")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin_activity_programme_edit", args=[self.activity.pk])).status_code,
            200,
        )

    def test_other_campus_activity_is_not_visible_to_campus_administrator(self):
        other_campus = Campus.objects.create(
            organization=self.campus.organization,
            name="Other Campus",
            is_active=True,
        )
        other_activity = Activity.objects.create(name="Other Club", campus=other_campus)
        role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        user = get_user_model().objects.create_user(username="phase8restricted", password="test-password")
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        response = self.client.get(reverse("admin_activity_programme_edit", args=[other_activity.pk]))
        self.assertEqual(response.status_code, 404)
