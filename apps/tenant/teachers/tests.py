from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import Role, User, UserRole

from .models import TeacherProfile


class TeacherCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Teacher Campus",
            is_active=True,
        )
        self.teacher = TeacherProfile.objects.create(
            first_name="Visible",
            last_name="Teacher",
            staff_id="T-VISIBLE",
            campus=self.campus,
        )
        self.hidden_teacher = TeacherProfile.objects.create(
            first_name="Hidden",
            last_name="Teacher",
            staff_id="T-HIDDEN",
            campus=self.other_campus,
        )

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="teacher_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_teacher_list_ignores_other_campus_filter(self):
        self.client.login(username="teacher_campus_admin", password="test-pass-123")

        response = self.client.get(reverse("admin_teachers_list"), {"campus": self.other_campus.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "T-VISIBLE")
        self.assertNotContains(response, "T-HIDDEN")

    def test_campus_admin_cannot_access_other_campus_teacher(self):
        self.client.login(username="teacher_campus_admin", password="test-pass-123")

        edit_response = self.client.get(reverse("admin_teachers_edit", kwargs={"pk": self.hidden_teacher.pk}))
        credentials_response = self.client.get(reverse("admin_teachers_credentials", kwargs={"pk": self.hidden_teacher.pk}))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(credentials_response.status_code, 404)

    def test_campus_admin_cannot_create_teacher_in_other_campus(self):
        self.client.login(username="teacher_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_teachers_create"),
            {
                "campus": self.other_campus.pk,
                "staff_id": "T-FORGED",
                "first_name": "Forged",
                "last_name": "Teacher",
                "phone": "",
                "email": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TeacherProfile.objects.filter(staff_id="T-FORGED").exists())

    def test_campus_admin_cannot_move_teacher_to_other_campus(self):
        self.client.login(username="teacher_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_teachers_edit", kwargs={"pk": self.teacher.pk}),
            {
                "campus": self.other_campus.pk,
                "staff_id": self.teacher.staff_id,
                "first_name": self.teacher.first_name,
                "last_name": self.teacher.last_name,
                "phone": "",
                "email": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.campus, self.campus)
