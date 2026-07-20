from django.test import TestCase

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import User

from .bulk_import import ImportRow, process_bulk_import
from .services import generate_next_student_id


class StudentNumberGenerationTests(TestCase):
    def setUp(self):
        self.organization = get_or_create_organization()

    def create_campus(self, *, name: str, code: str, number_format: str) -> Campus:
        return Campus.objects.create(
            organization=self.organization,
            name=name,
            code=code,
            student_number_format=number_format,
            is_active=True,
        )

    def test_trailing_zero_format_auto_increments(self):
        campus = self.create_campus(
            name="Legacy Number Campus",
            code="LGC",
            number_format="10/u/00",
        )

        self.assertEqual(generate_next_student_id(campus), "10/u/00")
        self.assertEqual(generate_next_student_id(campus), "10/u/01")
        self.assertEqual(generate_next_student_id(campus), "10/u/02")

        campus.refresh_from_db()
        self.assertEqual(campus.last_student_sequence, 3)

    def test_literal_format_without_sequence_receives_safe_suffix(self):
        campus = self.create_campus(
            name="Literal Number Campus",
            code="LIT",
            number_format="STUDENT",
        )

        self.assertEqual(generate_next_student_id(campus), "STUDENT-00001")
        self.assertEqual(generate_next_student_id(campus), "STUDENT-00002")

    def test_generator_skips_existing_username_when_counter_is_behind(self):
        campus = self.create_campus(
            name="Collision Number Campus",
            code="COL",
            number_format="{CAMPUS_CODE}-{SEQ:2}",
        )
        User.objects.create(username="COL-01")

        self.assertEqual(generate_next_student_id(campus), "COL-02")

        campus.refresh_from_db()
        self.assertEqual(campus.last_student_sequence, 2)

    def test_bulk_import_creates_three_incrementing_student_accounts(self):
        campus = self.create_campus(
            name="Bulk Number Campus",
            code="BLK",
            number_format="10/u/00",
        )
        administrator = User.objects.create_user(
            username="student_number_admin",
            password="test-pass-123",
        )
        rows = [
            ImportRow(
                row_number=index,
                first_name=first_name,
                last_name="Learner",
                date_of_birth="2010-05-15",
                email=None,
                campus_code=campus.code,
                errors=[],
            )
            for index, first_name in enumerate(
                ("First", "Second", "Third"),
                start=2,
            )
        ]

        result = process_bulk_import(
            rows=rows,
            default_campus=campus,
            campus_map={campus.code: campus},
            create_users=True,
            admin_user=administrator,
        )

        self.assertEqual(result.successful, 3)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.errors, [])
        self.assertEqual(
            [credential["username"] for credential in result.credentials],
            ["10/u/00", "10/u/01", "10/u/02"],
        )
