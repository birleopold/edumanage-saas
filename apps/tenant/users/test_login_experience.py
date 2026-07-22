from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Role, User


class LoginExperienceTests(TestCase):
    password = "Institutional-Test-Password-42"

    def setUp(self):
        self.user = User.objects.create_user(
            username="login-student",
            password=self.password,
            first_name="Amina",
        )
        role, _ = Role.objects.get_or_create(
            code=Role.STUDENT,
            defaults={"name": "Student"},
        )
        self.user.roles.add(role)

    def _login(self, next_url=None):
        data = {
            "username": self.user.username,
            "password": self.password,
            "remember_me": "on",
        }
        if next_url is not None:
            data["next"] = next_url
        with patch("apps.tenant.users.auth_views._audit_login"):
            return self.client.post(reverse("login"), data)

    def test_safe_next_destination_is_preserved_after_login(self):
        destination = f"{reverse('student_global_search')}?q=biology"

        response = self._login(destination)

        self.assertRedirects(response, destination, fetch_redirect_response=False)

    def test_external_next_destination_is_rejected(self):
        response = self._login("https://malicious.example/collect-session")

        self.assertRedirects(response, reverse("student_home"), fetch_redirect_response=False)

    def test_required_password_change_takes_priority_over_next(self):
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])

        response = self._login(reverse("student_global_search"))

        self.assertRedirects(response, reverse("change_password"), fetch_redirect_response=False)

    def test_login_page_keeps_return_destination_and_browser_guidance(self):
        destination = reverse("student_global_search")

        response = self.client.get(reverse("login"), {"next": destination})

        self.assertContains(response, f'name="next" value="{destination}"')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'id="password-visibility-toggle"')
        self.assertContains(response, "Avoid this on shared computers")
        self.assertContains(response, "prefers-reduced-motion")

    def test_remember_me_is_selected_by_default(self):
        response = self.client.get(reverse("login"))

        self.assertContains(
            response,
            f'name="remember_me" id="id_remember_me"',
        )
        self.assertContains(response, "checked")
