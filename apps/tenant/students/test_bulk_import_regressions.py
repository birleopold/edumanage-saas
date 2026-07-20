from datetime import date, datetime
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import User

from .bulk_import import parse_csv_file, parse_excel_file
from .models import StudentProfile


class StudentBulkImportDateTests(TestCase):
    def test_csv_accepts_common_spreadsheet_dates_and_normalizes_them(self):
        content = (
            "first_name,last_name,date_of_birth,email,campus_code\n"
            "John,Doe,5/15/2010,john.doe@example.com,MAIN\n"
            "Jane,Smith,8/22/2011,jane.smith@example.com,MAIN\n"
            "Bob,Johnson,12/3/2009,,MAIN\n"
        )
        uploaded = SimpleUploadedFile(
            "students.csv",
            content.encode("utf-8"),
            content_type="text/csv",
        )

        rows = parse_csv_file(uploaded, {"MAIN": object()})

        self.assertEqual(
            [row.date_of_birth for row in rows],
            [
                "2010-05-15",
                "2011-08-22",
                "2009-12-03",
            ],
        )
        self.assertTrue(all(row.is_valid() for row in rows))

    def test_excel_accepts_datetime_and_slash_dates_without_none_strings(self):
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["first_name", "last_name", "date_of_birth", "email", "campus_code"])
        sheet.append(["John", "Doe", datetime(2010, 5, 15), "john@example.com", "MAIN"])
        sheet.append(["Bob", "Johnson", "12/3/2009", None, "MAIN"])

        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)

        rows = parse_excel_file(stream, {"MAIN": object()})

        self.assertEqual(rows[0].date_of_birth, "2010-05-15")
        self.assertEqual(rows[1].date_of_birth, "2009-12-03")
        self.assertIsNone(rows[1].email)
        self.assertTrue(all(row.is_valid() for row in rows))


class StudentBulkImportPreviewPersistenceTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=organization).first()
        if self.campus is None:
            self.campus = Campus.objects.create(
                organization=organization,
                name="Bulk Import Campus",
                code="BULK",
                is_active=True,
                is_default=True,
            )
        elif not self.campus.code:
            self.campus.code = "BULK"
            self.campus.save(update_fields=["code"])

        if not self.campus.is_default:
            self.campus.is_default = True
            self.campus.save(update_fields=["is_default"])

        self.user = User.objects.create_user(
            username="bulk_import_admin",
            password="test-pass-123",
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        self.client.force_login(self.user)

    def test_confirm_uses_session_without_a_worker_local_cache_entry(self):
        uploaded = SimpleUploadedFile(
            "students.csv",
            (
                "first_name,last_name,date_of_birth,email,campus_code\n"
                f"John,Doe,5/15/2010,john.doe@example.com,{self.campus.code}\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        preview_response = self.client.post(
            reverse("admin_students_bulk_import"),
            {
                "action": "preview",
                "import_file": uploaded,
            },
        )

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.context["valid_count"], 1)
        preview_token = preview_response.context["preview_token"]

        self.assertIsNone(cache.get(f"student_bulk_import_v1:{preview_token}"))

        confirm_response = self.client.post(
            reverse("admin_students_bulk_import"),
            {
                "action": "confirm",
                "preview_token": preview_token,
            },
        )

        self.assertEqual(confirm_response.status_code, 302)
        self.assertEqual(
            confirm_response.url,
            reverse("admin_students_bulk_import_results"),
        )
        student = StudentProfile.objects.get(first_name="John", last_name="Doe")
        self.assertEqual(student.date_of_birth, date(2010, 5, 15))
