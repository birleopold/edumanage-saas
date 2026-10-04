from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.tenant.users.models import User


@override_settings(PLATFORM_2FA_REQUIRED=True)
class PlatformTwoFactorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="platform-owner",
            email="owner@example.com",
            password="StrongPass123!",
        )

    @patch("apps.public.tenants.platform_twofactor.send_mail", return_value=1)
    def test_superuser_login_requires_platform_verification(self, _send):
        response = self.client.post(reverse("platform_admin_login"), {
            "username": "platform-owner",
            "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("platform_verify_2fa"), fetch_redirect_response=False)

    @patch("apps.public.tenants.platform_twofactor.send_mail", return_value=1)
    def test_unverified_superuser_cannot_open_dashboard(self, _send):
        self.client.force_login(self.user)
        response = self.client.get(reverse("platform_dashboard"))
        self.assertRedirects(response, reverse("platform_verify_2fa"), fetch_redirect_response=False)

    def test_verified_superuser_can_open_dashboard(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["platform_2fa_verified"] = True
        session.save()
        response = self.client.get(reverse("platform_dashboard"))
        self.assertEqual(response.status_code, 200)
