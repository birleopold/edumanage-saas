from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .signals import synchronize_student_identity_on_login


class StudentLoginSignalTests(SimpleTestCase):
    @patch("apps.tenant.students.signals.StudentProfile.objects.filter")
    @patch("apps.tenant.students.signals.get_public_schema_name", return_value="public")
    def test_public_schema_login_does_not_query_student_table(self, _public_schema, student_filter):
        user = SimpleNamespace(is_superuser=False)

        with patch("apps.tenant.students.signals.connection.schema_name", "public", create=True):
            synchronize_student_identity_on_login(sender=object, request=None, user=user)

        student_filter.assert_not_called()

    @patch("apps.tenant.students.signals.StudentProfile.objects.filter")
    @patch("apps.tenant.students.signals.get_public_schema_name", return_value="public")
    def test_superuser_login_does_not_query_student_table(self, _public_schema, student_filter):
        user = SimpleNamespace(is_superuser=True)

        with patch("apps.tenant.students.signals.connection.schema_name", "school_demo", create=True):
            synchronize_student_identity_on_login(sender=object, request=None, user=user)

        student_filter.assert_not_called()

    @patch("apps.tenant.students.signals.sync_student_user_identity")
    @patch("apps.tenant.students.signals.StudentProfile.objects.filter")
    @patch("apps.tenant.students.signals.get_public_schema_name", return_value="public")
    def test_tenant_student_login_still_synchronizes_identity(
        self,
        _public_schema,
        student_filter,
        sync_identity,
    ):
        user = SimpleNamespace(is_superuser=False)
        student = object()
        student_filter.return_value.first.return_value = student

        with patch("apps.tenant.students.signals.connection.schema_name", "school_demo", create=True):
            synchronize_student_identity_on_login(sender=object, request=None, user=user)

        student_filter.assert_called_once_with(user=user)
        sync_identity.assert_called_once_with(student)
