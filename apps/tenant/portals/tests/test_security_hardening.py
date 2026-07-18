from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant.portals.campus_permissions import enforce_campus_scope, user_can_access_campus
from apps.tenant.portals.pwa import SERVICE_WORKER_JS


class CampusScopeFailClosedTests(SimpleTestCase):
    def test_unknown_role_receives_no_queryset_rows(self):
        user = SimpleNamespace(is_authenticated=True, is_superuser=False, has_role=lambda _role: False)
        queryset = MagicMock()
        empty_queryset = MagicMock()
        queryset.none.return_value = empty_queryset

        result = enforce_campus_scope(queryset, user)

        self.assertIs(result, empty_queryset)
        queryset.none.assert_called_once_with()

    @patch("apps.tenant.portals.campus_permissions.get_user_campus_scope", return_value=None)
    def test_unassigned_campus_admin_cannot_access_campus(self, _scope):
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_role=lambda role: role == "CAMPUS_ADMIN",
        )
        campus = SimpleNamespace(pk=1)
        self.assertFalse(user_can_access_campus(user, campus))


class PrivatePageCachingTests(SimpleTestCase):
    def test_service_worker_does_not_cache_attendance_navigation(self):
        self.assertNotIn('url.pathname.startsWith("/teacher/attendance', SERVICE_WORKER_JS)
        self.assertIn('fetch(request, { cache: "no-store" })', SERVICE_WORKER_JS)
        self.assertIn("indexedDB.deleteDatabase", SERVICE_WORKER_JS)
        self.assertIn("private pages", SERVICE_WORKER_JS.lower())
