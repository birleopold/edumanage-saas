from django.test import SimpleTestCase
from django.urls import reverse


class PlatformFormSecurityTests(SimpleTestCase):
    def test_platform_login_is_private_uncached_and_sets_csrf_cookie(self):
        response = self.client.get(reverse("platform_admin_login"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("private", cache_control)
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("must-revalidate", cache_control)
        self.assertIn("max-age=0", cache_control)
        self.assertEqual(response.headers.get("Pragma"), "no-cache")
        self.assertEqual(response.headers.get("Expires"), "0")

    def test_non_platform_pages_are_not_modified_by_platform_middleware(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.headers.get("Pragma"), "no-cache")
