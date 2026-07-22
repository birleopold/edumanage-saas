from django.test import TestCase

from apps.tenant.users.models import User

from .models import Campus
from .notification_forms import NotificationComposerForm


class NotificationComposerScopeTests(TestCase):
    def test_intentionally_empty_scoped_querysets_do_not_fall_back_to_all_rows(self):
        User.objects.create_user(username="outside-scope-user")

        form = NotificationComposerForm(
            campus_queryset=Campus.objects.none(),
            user_queryset=User.objects.none(),
        )

        self.assertEqual(form.fields["campus"].queryset.count(), 0)
        self.assertEqual(form.fields["recipient"].queryset.count(), 0)
