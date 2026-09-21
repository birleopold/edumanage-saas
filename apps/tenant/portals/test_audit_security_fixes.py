from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.tenant.finance.models import IntegrationApiKey, IntegrationApiKeyScope, IntegrationScope
from apps.tenant.users.models import PasswordSetupToken, Role, User, UserRole

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

    def test_teacher_directory_hides_peer_contact_details_and_other_campuses(self):
        from apps.tenant.orgsettings.models import Campus, OrganizationProfile
        from apps.tenant.teachers.models import TeacherProfile

        organization = OrganizationProfile.objects.create(name="Directory School")
        main = Campus.objects.create(
            organization=organization, name="Main", code="MAIN", is_default=True
        )
        annex = Campus.objects.create(
            organization=organization, name="Annex", code="ANNEX"
        )
        user = User.objects.create_user(username="directory-teacher")
        UserRole.objects.create(user=user, role=self.teacher_role)
        TeacherProfile.objects.create(
            user=user, first_name="Main", last_name="Teacher", campus=main
        )
        TeacherProfile.objects.create(
            first_name="Visible",
            last_name="Peer",
            campus=main,
            phone="0700000000",
            email="peer@example.com",
        )
        TeacherProfile.objects.create(
            first_name="Hidden", last_name="Annex", campus=annex
        )
        self.client.force_authenticate(user)

        response = self.client.get(reverse("api_mobile_teachers"))

        self.assertEqual(response.status_code, 200)
        teachers = response.json()["teachers"]
        self.assertEqual({row["name"] for row in teachers}, {"Teacher Main", "Peer Visible"})
        self.assertTrue(all("phone" not in row and "email" not in row for row in teachers))

    def test_multi_campus_admin_directory_includes_each_assigned_campus_only(self):
        from apps.tenant.orgsettings.models import Campus, OrganizationProfile
        from apps.tenant.teachers.models import TeacherProfile

        organization = OrganizationProfile.objects.create(name="Multi Campus School")
        campuses = [
            Campus.objects.create(
                organization=organization,
                name=name,
                code=code,
                is_default=index == 0,
            )
            for index, (name, code) in enumerate(
                (("Main", "MAIN"), ("Annex", "ANNEX"), ("Remote", "REMOTE"))
            )
        ]
        campus_role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"}
        )
        user = User.objects.create_user(username="directory-campus-admin")
        for campus in campuses[:2]:
            UserRole.objects.create(user=user, role=campus_role, campus=campus)
        for campus in campuses:
            TeacherProfile.objects.create(
                first_name=campus.name, last_name="Teacher", campus=campus
            )
        self.client.force_authenticate(user)

        response = self.client.get(reverse("api_mobile_teachers"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {row["campus"] for row in response.json()["teachers"]},
            {"Main", "Annex"},
        )


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

    def test_expired_integration_key_is_rejected(self):
        key, raw_key = IntegrationApiKey.create_with_plaintext(
            "Expired", expires_at=timezone.now() - timedelta(seconds=1)
        )
        scope, _ = IntegrationScope.objects.get_or_create(
            code="health-read", defaults={"name": "Read integration health"}
        )
        IntegrationApiKeyScope.objects.create(api_key=key, scope=scope)

        response = self.client.get(
            reverse("api_integrations_health"), HTTP_X_API_KEY=raw_key
        )

        self.assertEqual(response.status_code, 403)

    def test_integration_key_ip_allowlist_is_enforced(self):
        key, raw_key = IntegrationApiKey.create_with_plaintext(
            "Restricted", allowed_ip_addresses=["192.0.2.10"]
        )
        scope, _ = IntegrationScope.objects.get_or_create(
            code="health-read", defaults={"name": "Read integration health"}
        )
        IntegrationApiKeyScope.objects.create(api_key=key, scope=scope)

        denied = self.client.get(
            reverse("api_integrations_health"),
            HTTP_X_API_KEY=raw_key,
            REMOTE_ADDR="192.0.2.11",
        )
        allowed = self.client.get(
            reverse("api_integrations_health"),
            HTTP_X_API_KEY=raw_key,
            REMOTE_ADDR="192.0.2.10",
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
