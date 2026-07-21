from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from .forms import UserProfileForm
from .models import User


@override_settings(ROOT_URLCONF="config.urls")
class ProfileTemplateTests(SimpleTestCase):
    def test_administrator_profile_renders_all_security_links(self):
        user = User(username="school-owner", first_name="School", last_name="Owner")
        form = UserProfileForm(instance=user)

        html = render_to_string(
            "auth/profile.html",
            {
                "form": form,
                "user": user,
                "user_roles": [],
                "portal_base_template": "portals/admin/base.html",
                "portal_home_url": "/admin/",
                "portal_role_label": "Administrator",
                "can_manage_two_factor": True,
            },
        )

        self.assertIn("/change-password/", html)
        self.assertIn("/admin/audit/two-factor/", html)
        self.assertIn("/devices/", html)
        self.assertIn("/admin/", html)

    def test_non_administrator_profile_hides_admin_verification_settings(self):
        user = User(username="learner", first_name="School", last_name="Learner")
        form = UserProfileForm(instance=user)

        html = render_to_string(
            "auth/profile.html",
            {
                "form": form,
                "user": user,
                "user_roles": [],
                "portal_base_template": "portals/student/base.html",
                "portal_home_url": "/student/",
                "portal_role_label": "Student",
                "can_manage_two_factor": False,
            },
        )

        self.assertIn("/change-password/", html)
        self.assertNotIn("/admin/audit/two-factor/", html)
        self.assertIn("/devices/", html)
        self.assertIn("/student/", html)
