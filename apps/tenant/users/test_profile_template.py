from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from .forms import UserProfileForm
from .models import User


@override_settings(ROOT_URLCONF="config.urls")
class ProfileTemplateTests(SimpleTestCase):
    def test_profile_template_renders_all_security_links(self):
        user = User(username="school-owner", first_name="School", last_name="Owner")
        form = UserProfileForm(instance=user)

        html = render_to_string(
            "auth/profile.html",
            {"form": form, "user": user, "user_roles": []},
        )

        self.assertIn("/change-password/", html)
        self.assertIn("/admin/audit/two-factor/", html)
        self.assertIn("/devices/", html)
