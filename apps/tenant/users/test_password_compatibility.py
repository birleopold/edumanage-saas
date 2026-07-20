from django.test import TestCase

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.bulk_import import ImportRow, process_bulk_import
from apps.tenant.users.models import User

from .passwords import DIGITS, LOWERCASE, SPECIALS, UPPERCASE


class TemporaryPasswordCompatibilityTests(TestCase):
    def test_user_manager_exposes_secure_django4_compatible_method(self):
        password = User.objects.make_random_password(length=12)

        self.assertEqual(len(password), 12)
        self.assertTrue(any(character in UPPERCASE for character in password))
        self.assertTrue(any(character in LOWERCASE for character in password))
        self.assertTrue(any(character in DIGITS for character in password))
        self.assertTrue(any(character in SPECIALS for character in password))

    def test_bulk_student_account_creation_uses_compatible_password_method(self):
        organization = get_or_create_organization()
        campus = Campus.objects.filter(organization=organization).first()
        if campus is None:
            campus = Campus.objects.create(
                organization=organization,
                name="Password Test Campus",
                code="PWD",
                is_active=True,
                is_default=True,
            )

        administrator = User.objects.create_user(
            username="password_compat_admin",
            password="test-pass-123",
        )
        row = ImportRow(
            row_number=2,
            first_name="John",
            last_name="Doe",
            date_of_birth="2010-05-15",
            email="john.password.test@example.com",
            campus_code=campus.code or None,
            errors=[],
        )

        result = process_bulk_import(
            rows=[row],
            default_campus=campus,
            campus_map={campus.code: campus} if campus.code else {},
            create_users=True,
            admin_user=administrator,
        )

        self.assertEqual(result.successful, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.credentials), 1)

        credential = result.credentials[0]
        student = credential["student"]
        temporary_password = credential["temp_password"]

        self.assertIsNotNone(student.user_id)
        self.assertTrue(student.user.check_password(temporary_password))
        self.assertTrue(student.user.must_change_password)
