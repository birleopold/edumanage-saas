from django.test import TestCase
from django.urls import reverse

from apps.tenant.academics.models import Level
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.users.models import User

from .models import CampusEducationStage, EducationStage, LevelStageMapping
from .services import ensure_institution_profile, ensure_system_templates


class EducationFrameworkAdminViewTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Framework Portal School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
            is_active=True,
        )
        self.stages, self.frameworks = ensure_system_templates()
        self.profile = ensure_institution_profile(self.organization)
        self.admin = User.objects.create_superuser(
            username="framework_admin",
            email="framework-admin@example.com",
            password="test-pass-123",
        )
        self.client.login(username="framework_admin", password="test-pass-123")

    def test_dashboard_is_available_from_academics(self):
        response = self.client.get(reverse("admin_education_framework_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "One academic foundation")
        self.assertContains(response, self.organization.name)

    def test_sync_levels_action_preserves_existing_levels(self):
        level = Level.objects.create(name="Senior 4", order=20)

        response = self.client.post(
            reverse("admin_education_framework_dashboard"),
            {"action": "sync_levels"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Level.objects.get(pk=level.pk).name, "Senior 4")
        mapping = LevelStageMapping.objects.get(
            profile=self.profile,
            legacy_level_id=level.pk,
        )
        self.assertEqual(mapping.stage.code, EducationStage.LOWER_SECONDARY)

    def test_terminology_overrides_can_be_saved(self):
        response = self.client.post(
            reverse("admin_education_framework_terminology"),
            {
                "learner": "Pupil",
                "guardian": "Parent or Guardian",
                "external_exam": "UNEB or External Exam",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.terminology["learner"], "Pupil")
        self.assertEqual(
            self.profile.terminology["external_exam"],
            "UNEB or External Exam",
        )
        self.assertNotIn("class", self.profile.terminology)

    def test_profile_can_switch_to_international_framework(self):
        international = self.frameworks["INTERNATIONAL-CUSTOM"]

        response = self.client.post(
            reverse("admin_education_framework_profile"),
            {
                "institution_type": self.profile.MIXED,
                "country_code": "ke",
                "locale": "en-KE",
                "primary_framework": international.pk,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.country_code, "KE")
        self.assertEqual(self.profile.primary_framework, international)
        self.assertFalse(self.profile.use_local_terminology)

    def test_campus_stage_can_use_existing_grading_configuration(self):
        response = self.client.post(
            reverse("admin_campus_education_stage_create"),
            {
                "campus": self.campus.pk,
                "stage": self.stages[EducationStage.PRIMARY].pk,
                "local_name": "Primary",
                "academic_period_type": EducationStage.PERIOD_TERM,
                "report_layout_key": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        campus_stage = CampusEducationStage.objects.get(
            profile=self.profile,
            campus=self.campus,
            stage=self.stages[EducationStage.PRIMARY],
        )
        self.assertEqual(campus_stage.framework_stage.framework, self.profile.primary_framework)
        self.assertEqual(campus_stage.local_name, "Primary")
