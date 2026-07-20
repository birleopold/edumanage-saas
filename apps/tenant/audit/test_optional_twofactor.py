from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .twofactor import user_needs_2fa


class OptionalAdministratorTwoFactorTests(SimpleTestCase):
    def _admin(self):
        return SimpleNamespace(
            is_authenticated=True,
            has_role=lambda role: role == "ADMIN",
        )

    @override_settings(ADMIN_2FA_REQUIRED=False)
    @patch("apps.tenant.audit.twofactor.UserTwoFactorSetting.objects.filter")
    def test_otp_is_off_when_account_has_not_enabled_it(self, filter_mock):
        filter_mock.return_value.exists.return_value = False
        admin = self._admin()

        self.assertFalse(user_needs_2fa(admin))
        filter_mock.assert_called_once_with(user=admin, is_enabled=True)

    @override_settings(ADMIN_2FA_REQUIRED=False)
    @patch("apps.tenant.audit.twofactor.UserTwoFactorSetting.objects.filter")
    def test_otp_is_required_after_account_enables_it(self, filter_mock):
        filter_mock.return_value.exists.return_value = True

        self.assertTrue(user_needs_2fa(self._admin()))

    @override_settings(ADMIN_2FA_REQUIRED=True)
    @patch("apps.tenant.audit.twofactor.UserTwoFactorSetting.objects.filter")
    def test_platform_can_still_enforce_otp_emergency_override(self, filter_mock):
        self.assertTrue(user_needs_2fa(self._admin()))
        filter_mock.assert_not_called()
