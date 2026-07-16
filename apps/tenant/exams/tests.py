from django.test import TestCase
from django.urls import reverse

from apps.tenant.users.models import Role, User


class StudentExamAccessTests(TestCase):
    def test_student_role_without_profile_gets_forbidden_not_server_error(self):
        role, _ = Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})
        user = User.objects.create_user(username="student_without_profile", password="test-pass-123")
        user.roles.add(role)

        self.client.login(username="student_without_profile", password="test-pass-123")
        response = self.client.get(reverse("student_exams_dashboard"))

        self.assertEqual(response.status_code, 403)
