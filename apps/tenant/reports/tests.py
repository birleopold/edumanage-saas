from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole


class ReportsCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Reports Campus",
            is_active=True,
        )
        StudentProfile.objects.create(
            first_name="Visible",
            last_name="Student",
            student_id="RP-VISIBLE",
            campus=self.campus,
        )
        StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Student",
            student_id="RP-HIDDEN",
            campus=self.other_campus,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="reports_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_overview_ignores_forged_campus_filter(self):
        self.client.login(username="reports_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_reports_overview"), {"campus": self.other_campus.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.campus.name)
        self.assertNotContains(response, self.other_campus.name)
        self.assertEqual(response.context["selected_campus_id"], self.campus.pk)

    def test_campus_admin_overview_csv_ignores_forged_campus_filter(self):
        self.client.login(username="reports_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_reports_overview_csv"), {"campus": self.other_campus.pk})
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"Campus,{self.campus.name}", content)
        self.assertIn("Students (total),1", content)
        self.assertNotIn(self.other_campus.name, content)
