from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from .feature_gate import FeatureGateMiddleware


class FeatureGateSecurityRouteTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = FeatureGateMiddleware(lambda request: HttpResponse("ok"))

    def _blocked_feature(self, path):
        request = self.factory.get(path)
        with (
            patch(
                "apps.tenant.orgsettings.feature_gate.connection",
                SimpleNamespace(schema_name="demo"),
            ),
            patch("apps.tenant.orgsettings.feature_gate.get_organization", return_value=object()),
            patch("apps.tenant.orgsettings.feature_gate.get_current_campus", return_value=None),
            patch(
                "apps.tenant.orgsettings.feature_gate.get_feature_flags",
                return_value={"AUDIT": False},
            ),
        ):
            return self.middleware._blocked_feature(request)

    def test_two_factor_verification_remains_available_when_audit_is_disabled(self):
        self.assertIsNone(self._blocked_feature("/admin/audit/verify/"))

    def test_privacy_acceptance_remains_available_when_audit_is_disabled(self):
        self.assertIsNone(self._blocked_feature("/admin/audit/accept/"))

    def test_optional_audit_dashboard_remains_blocked_when_audit_is_disabled(self):
        self.assertEqual(self._blocked_feature("/admin/audit/"), "AUDIT")
