from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Activity, ActivityMember


class ActivityAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Activity Campus",
            is_active=True,
        )
        self.activity = Activity.objects.create(
            name="Visible Activity",
            type=Activity.CLUB,
            campus=self.campus,
            is_active=True,
        )
        self.hidden_activity = Activity.objects.create(
            name="Hidden Activity",
            type=Activity.SPORT,
            campus=self.other_campus,
            is_active=True,
        )
        self.shared_activity = Activity.objects.create(
            name="Shared Activity",
            type=Activity.GENERAL,
            campus=None,
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Student",
            student_id="ACT-VISIBLE",
            campus=self.campus,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Student",
            student_id="ACT-HIDDEN",
            campus=self.other_campus,
        )
        self.member = ActivityMember.objects.create(activity=self.activity, student=self.student)
        self.hidden_member = ActivityMember.objects.create(activity=self.shared_activity, student=self.hidden_student)

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="activity_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_activity_list_sees_own_and_shared_only(self):
        self.client.login(username="activity_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_activities_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Activity")
        self.assertContains(response, "Shared Activity")
        self.assertNotContains(response, "Hidden Activity")

    def test_campus_admin_cannot_edit_other_or_shared_activity(self):
        self.client.login(username="activity_campus_admin", password="test-pass-123")

        hidden_response = self.client.get(reverse("admin_activities_edit", kwargs={"pk": self.hidden_activity.pk}))
        shared_response = self.client.get(reverse("admin_activities_edit", kwargs={"pk": self.shared_activity.pk}))

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(shared_response.status_code, 404)

    def test_campus_admin_cannot_create_or_move_activity_to_other_campus(self):
        self.client.login(username="activity_campus_admin", password="test-pass-123")

        create_response = self.client.post(
            reverse("admin_activities_create"),
            {
                "name": "Forged Activity",
                "type": Activity.CLUB,
                "description": "",
                "campus": self.other_campus.pk,
                "head": "",
                "meeting_day": "",
                "meeting_time": "",
                "location": "",
                "is_active": "on",
            },
        )
        edit_response = self.client.post(
            reverse("admin_activities_edit", kwargs={"pk": self.activity.pk}),
            {
                "name": self.activity.name,
                "type": self.activity.type,
                "description": self.activity.description,
                "campus": self.other_campus.pk,
                "head": "",
                "meeting_day": self.activity.meeting_day,
                "meeting_time": self.activity.meeting_time,
                "location": self.activity.location,
                "is_active": "on",
            },
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)
        self.assertFalse(Activity.objects.filter(name="Forged Activity").exists())
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.campus, self.campus)

    def test_campus_admin_cannot_add_other_campus_student_to_activity(self):
        self.client.login(username="activity_campus_admin", password="test-pass-123")

        hidden_response = self.client.post(
            reverse("admin_activities_member_add", kwargs={"pk": self.activity.pk}),
            {"student_id": self.hidden_student.pk},
        )
        visible_response = self.client.post(
            reverse("admin_activities_member_add", kwargs={"pk": self.shared_activity.pk}),
            {"student_id": self.student.pk},
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(visible_response.status_code, 302)
        self.assertFalse(ActivityMember.objects.filter(activity=self.activity, student=self.hidden_student).exists())
        self.assertTrue(ActivityMember.objects.filter(activity=self.shared_activity, student=self.student, is_active=True).exists())

    def test_campus_admin_cannot_remove_other_campus_membership_from_shared_activity(self):
        self.client.login(username="activity_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse(
                "admin_activities_member_remove",
                kwargs={"pk": self.shared_activity.pk, "member_id": self.hidden_member.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.hidden_member.refresh_from_db()
        self.assertTrue(self.hidden_member.is_active)
