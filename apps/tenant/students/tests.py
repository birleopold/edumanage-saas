from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, User, UserRole

from .models import StudentProfile


class StudentCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Student Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Student",
            student_id="ST-VISIBLE",
            campus=self.campus,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Student",
            student_id="ST-HIDDEN",
            campus=self.other_campus,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="student_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_student_list_and_export_ignore_other_campus_filter(self):
        self.client.login(username="student_campus_admin", password="test-pass-123")

        list_response = self.client.get(reverse("admin_students_list"), {"campus": self.other_campus.pk})
        export_response = self.client.get(reverse("admin_students_export_csv"), {"campus": self.other_campus.pk})

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "ST-VISIBLE")
        self.assertNotContains(list_response, "ST-HIDDEN")
        self.assertContains(export_response, "ST-VISIBLE")
        self.assertNotContains(export_response, "ST-HIDDEN")

    def test_campus_admin_cannot_access_other_campus_student_detail_or_credentials(self):
        self.client.login(username="student_campus_admin", password="test-pass-123")

        detail_response = self.client.get(reverse("admin_students_edit", kwargs={"pk": self.hidden_student.pk}))
        credentials_response = self.client.get(reverse("admin_students_credentials", kwargs={"pk": self.hidden_student.pk}))
        id_card_response = self.client.get(reverse("admin_students_id_card_pdf", kwargs={"pk": self.hidden_student.pk}))

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(credentials_response.status_code, 404)
        self.assertEqual(id_card_response.status_code, 404)

    def test_campus_admin_cannot_create_student_in_other_campus(self):
        self.client.login(username="student_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_students_create"),
            {
                "campus": self.other_campus.pk,
                "student_id": "ST-FORGED",
                "first_name": "Forged",
                "last_name": "Student",
                "email": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(StudentProfile.objects.filter(student_id="ST-FORGED").exists())

    def test_campus_admin_cannot_move_student_to_other_campus(self):
        self.client.login(username="student_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_students_edit", kwargs={"pk": self.student.pk}),
            {
                "campus": self.other_campus.pk,
                "student_id": self.student.student_id,
                "first_name": self.student.first_name,
                "last_name": self.student.last_name,
                "email": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.campus, self.campus)
