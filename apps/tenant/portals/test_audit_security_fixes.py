from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.tenant.finance.models import IntegrationApiKey, IntegrationApiKeyScope, IntegrationScope
from apps.tenant.users.models import PasswordSetupToken, Role, User

from .mobile_api_serializers import AttendanceMarkSerializer
from .mobile_api_serializers import StudentSummarySerializer


class PasswordSetupTokenSecurityTests(TestCase):
    def test_raw_bearer_token_is_not_stored(self):
        user = User.objects.create_user(username="setup-user")
        setup_token = PasswordSetupToken.create_for_user(user)

        self.assertNotEqual(setup_token.raw_token, setup_token.token_digest)
        self.assertNotIn(setup_token.raw_token, setup_token.token_digest)
        self.assertEqual(PasswordSetupToken.resolve(setup_token.raw_token), setup_token)


class MobileAuthorizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.parent_role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
        self.teacher_role, _ = Role.objects.get_or_create(code=Role.TEACHER, defaults={"name": "Teacher"})

    def test_parent_cannot_list_all_teachers(self):
        user = User.objects.create_user(username="mobile-parent")
        user.roles.add(self.parent_role)
        self.client.force_authenticate(user)

        response = self.client.get(reverse("api_mobile_teachers"))

        self.assertEqual(response.status_code, 403)

    def test_teacher_role_can_open_teacher_directory(self):
        user = User.objects.create_user(username="mobile-teacher")
        user.roles.add(self.teacher_role)
        self.client.force_authenticate(user)

        response = self.client.get(reverse("api_mobile_teachers"))

        self.assertEqual(response.status_code, 200)

    def test_attendance_payload_rejects_duplicate_student(self):
        serializer = AttendanceMarkSerializer(
            data={
                "entries": [
                    {"student_id": 7, "status": "PRESENT"},
                    {"student_id": 7, "status": "ABSENT"},
                ]
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("entries", serializer.errors)

    def test_student_serializer_exposes_only_reviewed_fields(self):
        from apps.tenant.students.models import StudentProfile

        student = StudentProfile.objects.create(
            first_name="Amina",
            last_name="Kato",
            email="amina@example.com",
            nin="sensitive-nin",
        )

        payload = StudentSummarySerializer(student).data

        self.assertEqual(
            set(payload),
            {"id", "student_id", "name", "email", "campus", "stream", "class_group"},
        )
        self.assertNotIn("nin", payload)


class IntegrationScopeTests(TestCase):
    def test_message_logs_require_matching_scope(self):
        key, raw_key = IntegrationApiKey.create_with_plaintext("Health only")
        scope, _ = IntegrationScope.objects.get_or_create(
            code="health-read", defaults={"name": "Read integration health"}
        )
        IntegrationApiKeyScope.objects.create(api_key=key, scope=scope)

        health = self.client.get(reverse("api_integrations_health"), HTTP_X_API_KEY=raw_key)
        logs = self.client.get(reverse("api_integrations_message_logs"), HTTP_X_API_KEY=raw_key)

        self.assertEqual(health.status_code, 200)
        self.assertEqual(logs.status_code, 403)
