from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.models import Role, UserRole

from .models import AssessmentType, AssessmentWeightingScheme
from .services import ensure_assessment_type_templates


class AssessmentFrameworkViewTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="View Test School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="phase2admin",
            email="phase2@example.com",
            password="test-password",
        )
        self.client.force_login(self.superuser)
        ensure_assessment_type_templates()

    def test_dashboard_is_available_to_full_administrator(self):
        response = self.client.get(reverse("admin_assessment_framework_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assessment types and weighting")
        self.assertContains(response, "EOT")

    def test_create_scheme_from_setup_ui(self):
        response = self.client.post(
            reverse("admin_weighting_scheme_create"),
            {
                "code": "PRIMARY-DEFAULT",
                "name": "Primary Default",
                "total_weight": "100.00",
                "missing_score_policy": AssessmentWeightingScheme.REQUIRE_COMPLETE,
                "normalize_to_total": "on",
                "priority": "10",
                "is_default": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AssessmentWeightingScheme.objects.filter(code="PRIMARY-DEFAULT").exists())

    def test_campus_administrator_cannot_change_institution_wide_framework(self):
        role = Role.objects.create(code=Role.CAMPUS_ADMIN, name="Campus Admin")
        campus_admin = get_user_model().objects.create_user(
            username="campusadmin",
            password="test-password",
        )
        UserRole.objects.create(user=campus_admin, role=role, campus=self.campus)
        self.client.force_login(campus_admin)

        response = self.client.get(reverse("admin_assessment_framework_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_system_assessment_type_code_is_normalized(self):
        response = self.client.post(
            reverse("admin_assessment_type_create"),
            {
                "code": " custom oral ",
                "name": "Custom Oral",
                "kind": AssessmentType.ORAL,
                "description": "",
                "local_aliases": "{}",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AssessmentType.objects.filter(code="CUSTOM-ORAL").exists())
