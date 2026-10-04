from django.test import SimpleTestCase

from apps.tenant.audit.services import safe_params


class AuditRedactionTests(SimpleTestCase):
    def test_oauth_and_authentication_secrets_are_redacted(self):
        params = {
            "code": "oauth-code",
            "access_token": "access",
            "refresh-token": "refresh",
            "Authorization": "Bearer secret",
            "client_secret": "client",
            "ordinary": "visible",
        }
        safe = safe_params(params)
        self.assertEqual(safe["ordinary"], "visible")
        for key in ("code", "access_token", "refresh-token", "Authorization", "client_secret"):
            self.assertEqual(safe[key], "***")
