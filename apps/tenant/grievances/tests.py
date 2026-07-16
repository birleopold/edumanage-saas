from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, User, UserRole

from .models import Grievance


class GrievanceAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Grievance Campus",
            is_active=True,
        )
        self.submitter = User.objects.create_user(username="grievance_submitter", password="test-pass-123")
        self.grievance = Grievance.objects.create(
            campus=self.campus,
            submitted_by=self.submitter,
            subject="Visible grievance",
            body="Visible body",
        )
        self.hidden_grievance = Grievance.objects.create(
            campus=self.other_campus,
            submitted_by=self.submitter,
            subject="Hidden grievance",
            body="Hidden body",
        )
        self.unassigned_grievance = Grievance.objects.create(
            campus=None,
            submitted_by=self.submitter,
            subject="Unassigned grievance",
            body="Unassigned body",
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="grievance_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_list_sees_own_and_unassigned_grievances_only(self):
        self.client.login(username="grievance_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_grievances_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible grievance")
        self.assertContains(response, "Unassigned grievance")
        self.assertNotContains(response, "Hidden grievance")

    def test_campus_admin_cannot_access_other_campus_grievance(self):
        self.client.login(username="grievance_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_grievances_detail", kwargs={"pk": self.hidden_grievance.pk}))

        self.assertEqual(response.status_code, 404)

    def test_campus_admin_can_update_scoped_grievance(self):
        self.client.login(username="grievance_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_grievances_detail", kwargs={"pk": self.grievance.pk}),
            {
                "status": self.grievance.status,
                "resolution_notes": "Reviewed by campus admin.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.grievance.refresh_from_db()
        self.assertEqual(self.grievance.handled_by, self.user)
        self.assertEqual(self.grievance.resolution_notes, "Reviewed by campus admin.")
