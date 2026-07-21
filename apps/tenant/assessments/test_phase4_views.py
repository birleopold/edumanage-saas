from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import GradeRange, GradingScale
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.models import Role, UserRole

from .models import GradingProfile, ReportRule


class Phase4GradingFrameworkViewTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Phase 4 View School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.scale = GradingScale.objects.create(name="Default Scale", is_default=True, is_active=True)
        GradeRange.objects.create(scale=self.scale, grade="A", min_score=80, max_score=100, remark="Excellent")
        GradeRange.objects.create(scale=self.scale, grade="B", min_score=70, max_score=79.99, remark="Very good")
        GradeRange.objects.create(scale=self.scale, grade="C", min_score=60, max_score=69.99, remark="Good")
        GradeRange.objects.create(scale=self.scale, grade="D", min_score=50, max_score=59.99, remark="Fair")
        GradeRange.objects.create(scale=self.scale, grade="F", min_score=0, max_score=49.99, remark="Needs support")
        self.superuser = get_user_model().objects.create_superuser(
            username="phase4admin",
            email="phase4@example.com",
            password="test-password",
        )
        self.client.force_login(self.superuser)

    def test_dashboard_is_available_to_full_administrator(self):
        response = self.client.get(reverse("admin_grading_framework_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Level-specific grading and report rules")

    def test_bootstrap_creates_default_profile_without_changing_scale(self):
        response = self.client.post(
            reverse("admin_grading_framework_dashboard"),
            {"action": "bootstrap"},
        )
        self.assertEqual(response.status_code, 302)
        profile = GradingProfile.objects.get(code="DEFAULT-GRADING")
        self.assertEqual(profile.grading_scale, self.scale)
        self.assertTrue(ReportRule.objects.filter(grading_profile=profile).exists())
        self.scale.refresh_from_db()
        self.assertTrue(self.scale.is_default)

    def test_create_profile_normalizes_code(self):
        response = self.client.post(
            reverse("admin_grading_profile_create"),
            {
                "code": " senior one ",
                "name": "Senior One",
                "description": "",
                "grading_scale": self.scale.pk,
                "overall_aggregation": GradingProfile.MEAN,
                "incomplete_result_policy": GradingProfile.EXCLUDE_INCOMPLETE,
                "pass_percentage": "50",
                "decimal_places": "2",
                "priority": "10",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GradingProfile.objects.filter(code="SENIOR-ONE").exists())

    def test_campus_administrator_cannot_change_institution_wide_grading_rules(self):
        role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={"name": "Campus Admin"},
        )
        user = get_user_model().objects.create_user(
            username="phase4campusadmin",
            password="test-password",
        )
        UserRole.objects.create(user=user, role=role, campus=self.campus)
        self.client.force_login(user)

        response = self.client.get(reverse("admin_grading_framework_dashboard"))

        self.assertEqual(response.status_code, 403)
