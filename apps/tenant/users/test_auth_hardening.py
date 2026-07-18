from django.contrib.auth import get_user_model
from django.test import TestCase

from .backends import EmailOrUsernameModelBackend


class AmbiguousEmailAuthenticationTests(TestCase):
    def test_duplicate_email_does_not_authenticate(self):
        user_model = get_user_model()
        first = user_model.objects.create_user(
            username="first",
            email="same@example.com",
            password="correct-password",
        )
        duplicate = user_model(
            username="second",
            email="same@example.com",
            password=first.password,
            is_active=True,
        )
        user_model.objects.bulk_create([duplicate])

        authenticated = EmailOrUsernameModelBackend().authenticate(
            request=None,
            username="same@example.com",
            password="correct-password",
        )

        self.assertIsNone(authenticated)
