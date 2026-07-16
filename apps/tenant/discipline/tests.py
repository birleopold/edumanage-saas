from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole

from .models import Incident


class DisciplineCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Discipline Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Discipline",
            student_id="DISC-VISIBLE",
            campus=self.campus,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Discipline",
            student_id="DISC-HIDDEN",
            campus=self.other_campus,
        )
        self.incident = Incident.objects.create(
            student=self.student,
            title="Visible incident",
            category="Conduct",
        )
        self.hidden_incident = Incident.objects.create(
            student=self.hidden_student,
            title="Hidden incident",
            category="Conduct",
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="discipline_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_incident_list_is_scoped(self):
        self.client.login(username="discipline_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_incidents_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible incident")
        self.assertNotContains(response, "Hidden incident")

    def test_campus_admin_cannot_access_other_campus_incident(self):
        self.client.login(username="discipline_campus_admin", password="test-pass-123")

        detail_response = self.client.get(reverse("admin_incidents_detail", kwargs={"pk": self.hidden_incident.pk}))
        edit_response = self.client.get(reverse("admin_incidents_edit", kwargs={"pk": self.hidden_incident.pk}))
        action_response = self.client.post(
            reverse("admin_incidents_detail", kwargs={"pk": self.hidden_incident.pk}),
            {"action": "Follow up", "note": "Should not save"},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(action_response.status_code, 404)
        self.assertEqual(self.hidden_incident.actions.count(), 0)

    def test_campus_admin_cannot_create_incident_for_other_campus_student(self):
        self.client.login(username="discipline_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_incidents_create"),
            {
                "student": self.hidden_student.pk,
                "title": "Forged incident",
                "category": "Conduct",
                "severity": Incident.MEDIUM,
                "description": "",
                "status": Incident.OPEN,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Incident.objects.filter(title="Forged incident").exists())

    def test_campus_admin_cannot_move_incident_to_other_campus_student(self):
        self.client.login(username="discipline_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_incidents_edit", kwargs={"pk": self.incident.pk}),
            {
                "student": self.hidden_student.pk,
                "title": self.incident.title,
                "category": self.incident.category,
                "severity": self.incident.severity,
                "description": "",
                "status": self.incident.status,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.student, self.student)
