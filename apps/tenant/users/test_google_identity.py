from django.test import TestCase, override_settings
from django.urls import reverse

from apps.public.tenants.models import Domain, GoogleLoginHandoff, GoogleOAuthTransaction, Tenant


@override_settings(
    GOOGLE_OAUTH_ENABLED=True,
    GOOGLE_OAUTH_CLIENT_ID="test-client",
    GOOGLE_OAUTH_CLIENT_SECRET="test-secret",
    GOOGLE_OAUTH_REDIRECT_URI="https://edumanage.leosoftug.com/auth/google/callback/",
)
class GoogleIdentityTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(schema_name="google_test", name="Google Test", status="active")
        self.domain = Domain.objects.create(domain="google-test.example.com", tenant=self.tenant, is_primary=True)

    def test_google_start_uses_central_callback_and_persists_state(self):
        response = self.client.get(reverse("google_oauth_start"), HTTP_HOST=self.domain.domain)
        self.assertEqual(response.status_code, 302)
        self.assertIn("redirect_uri=https%3A%2F%2Fedumanage.leosoftug.com%2Fauth%2Fgoogle%2Fcallback%2F", response["Location"])
        tx = GoogleOAuthTransaction.objects.get()
        self.assertEqual(tx.tenant_id, self.tenant.id)
        self.assertEqual(tx.return_domain_id, self.domain.id)
        self.assertNotIn("state=", tx.state_digest)

    def test_unregistered_domain_cannot_start_google(self):
        response = self.client.get(reverse("google_oauth_start"), HTTP_HOST="unknown.example.com")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    def test_handoff_is_bound_to_tenant_and_domain(self):
        self.assertEqual(GoogleLoginHandoff.objects.count(), 0)

    def test_disabled_google_signin_returns_to_password_login(self):
        with override_settings(GOOGLE_OAUTH_ENABLED=False):
            response = self.client.get(reverse("google_oauth_start"), HTTP_HOST=self.domain.domain)
        self.assertRedirects(response, reverse("login"))
