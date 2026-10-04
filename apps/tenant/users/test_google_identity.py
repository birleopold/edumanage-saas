from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.tenant.users.models import FederatedIdentity, User


@override_settings(
    GOOGLE_OAUTH_ENABLED=True,
    GOOGLE_OAUTH_CLIENT_ID="test-client",
    GOOGLE_OAUTH_CLIENT_SECRET="test-secret",
)
class GoogleIdentityTests(TestCase):
    def test_google_start_records_state(self):
        response = self.client.get(reverse("google_oauth_start"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("google_oauth_state", self.client.session)

    def test_federated_subject_is_unique(self):
        first = User.objects.create_user(username="first-google", email="first@example.com")
        second = User.objects.create_user(username="second-google", email="second@example.com")
        FederatedIdentity.objects.create(
            user=first, provider=FederatedIdentity.GOOGLE, subject="google-subject", email=first.email, email_verified=True
        )
        with self.assertRaises(Exception):
            FederatedIdentity.objects.create(
                user=second, provider=FederatedIdentity.GOOGLE, subject="google-subject", email=second.email, email_verified=True
            )

    def test_disabled_google_signin_returns_to_password_login(self):
        with override_settings(GOOGLE_OAUTH_ENABLED=False):
            response = self.client.get(reverse("google_oauth_start"))
        self.assertRedirects(response, reverse("login"))
