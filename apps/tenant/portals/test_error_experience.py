from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.tenant.audit.request_ids import REQUEST_ID_HEADER
from apps.tenant.users.models import Role, User

from .error_handlers import csrf_failure, handler404, handler500


class BrokenAuthenticationUser:
    @property
    def is_authenticated(self):
        raise RuntimeError("Authentication storage unavailable")


@override_settings(SUPPORT_CONTACT_EMAIL="support@example.com")
class ErrorExperienceTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.original_schema_name = getattr(connection, "schema_name", None)
        connection.schema_name = "public"

    def tearDown(self):
        if self.original_schema_name is None:
            try:
                del connection.schema_name
            except AttributeError:
                pass
        else:
            connection.schema_name = self.original_schema_name

    def _student_user(self):
        user = User.objects.create_user(
            username="student-error-test",
            password="not-used",
        )
        role, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        user.roles.add(role)
        return user

    def test_authenticated_student_404_returns_to_student_dashboard(self):
        request = self.factory.get("/student/missing-page/")
        request.user = self._student_user()
        request.request_id = "req-student-404"

        response = handler404(request)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, reverse("student_home"), status_code=404)
        self.assertContains(response, "req-student-404", status_code=404)
        self.assertEqual(response[REQUEST_ID_HEADER], "req-student-404")
        self.assertContains(
            response,
            "Technical details are hidden to protect the school system",
            status_code=404,
        )
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_csrf_failure_explains_that_nothing_was_saved(self):
        request = self.factory.post("/parent/account/message-preferences/")
        request.user = AnonymousUser()

        response = csrf_failure(request, reason="CSRF cookie missing")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Your form session expired", status_code=403)
        self.assertContains(response, "No changes were saved", status_code=403)
        self.assertContains(response, "Open the form again", status_code=403)
        self.assertNotContains(response, "CSRF cookie missing", status_code=403)
        self.assertEqual(response[REQUEST_ID_HEADER], request.request_id)

    def test_server_error_shows_safe_support_reference(self):
        request = self.factory.get("/admin/reports/")
        request.user = AnonymousUser()
        request.request_id = "req-safe-500"

        response = handler500(request)

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "req-safe-500", status_code=500)
        self.assertContains(response, "support@example.com", status_code=500)
        self.assertContains(
            response,
            "technical details have been kept private",
            status_code=500,
        )

    def test_server_error_still_renders_when_authentication_storage_fails(self):
        request = self.factory.get("/admin/reports/")
        request.user = BrokenAuthenticationUser()
        request.request_id = "req-auth-storage-fault"

        response = handler500(request)

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "req-auth-storage-fault", status_code=500)
        self.assertContains(response, "Sign in", status_code=500)
        self.assertNotContains(
            response,
            "Authentication storage unavailable",
            status_code=500,
        )
