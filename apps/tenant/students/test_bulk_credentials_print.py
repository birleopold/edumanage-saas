from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.users.models import User

from .bulk_views import BULK_IMPORT_CREDENTIALS_KEY, BULK_IMPORT_RESULT_KEY


class BulkCredentialPrintTests(TestCase):
    def setUp(self):
        organization = get_or_create_organization()
        organization.name = "Demo School"
        organization.save(update_fields=["name"])

        campus = Campus.objects.filter(organization=organization).first()
        if campus is None:
            campus = Campus.objects.create(
                organization=organization,
                name="Main Campus",
                code="MAIN",
                is_active=True,
                is_default=True,
            )
        elif not campus.is_default:
            campus.is_default = True
            campus.save(update_fields=["is_default"])

        self.user = User.objects.create_user(
            username="bulk_print_admin",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

        session = self.client.session
        session[BULK_IMPORT_CREDENTIALS_KEY] = [
            {
                "student_id": 1,
                "student_number": "10/u/01",
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com",
                "temp_password": "Temp#Pass42",
                "has_setup_token": True,
            },
            {
                "student_id": 2,
                "student_number": "10/u/02",
                "first_name": "Bob",
                "last_name": "Johnson",
                "email": "",
                "temp_password": "Other#Pass7",
                "has_setup_token": False,
            },
        ]
        session[BULK_IMPORT_RESULT_KEY] = {"successful": 2, "failed": 1}
        session.save()

    def test_print_route_renders_credentials_only_without_admin_chrome(self):
        response = self.client.get(reverse("admin_students_print_bulk_credentials"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "portals/admin/students/bulk_credentials_print.html",
        )
        self.assertContains(response, "Student Portal Login Credentials")
        self.assertContains(response, "10/u/01")
        self.assertContains(response, "Temp#Pass42")
        self.assertContains(response, "Demo School")
        self.assertContains(response, "window.print()")
        self.assertNotContains(response, "School Admin Area")
        self.assertNotContains(response, "Import Results")
        self.assertNotContains(response, "Row 2:")

    def test_results_page_links_to_print_sheet_and_reports_partial_failure(self):
        response = self.client.get(reverse("admin_students_bulk_import_results"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import completed with warnings")
        self.assertContains(response, "2 student(s) imported successfully")
        self.assertContains(response, "1 row(s) failed")
        self.assertContains(
            response,
            reverse("admin_students_print_bulk_credentials"),
        )
        self.assertNotContains(response, 'onclick="window.print()"')
