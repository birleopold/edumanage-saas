from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant.academics.models import GradingScale
from apps.tenant.orgsettings.models import Campus, OrganizationProfile

from .configuration import framework_readiness
from .models import CampusEducationStage, EducationStage, FrameworkStage
from .services import ensure_institution_profile, ensure_system_templates


class CampusEducationStagePolicyTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(
            name="Stage Policy School"
        )
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
            is_active=True,
        )
        self.stages, self.frameworks = ensure_system_templates()
        self.profile = ensure_institution_profile(self.organization)
        self.profile.primary_framework = self.frameworks["UG-NATIONAL"]
        self.profile.save(update_fields=["primary_framework", "updated_at"])
        self.primary_stage = self.stages[EducationStage.PRIMARY]
        self.framework_stage = FrameworkStage.objects.get(
            framework=self.profile.primary_framework,
            stage=self.primary_stage,
        )

    def make_stage(self, **overrides):
        values = {
            "profile": self.profile,
            "campus": self.campus,
            "stage": self.primary_stage,
            "framework_stage": self.framework_stage,
        }
        values.update(overrides)
        return CampusEducationStage(**values)

    def test_real_grading_scale_relation_keeps_legacy_snapshot(self):
        scale = GradingScale.objects.create(
            name="Primary Scale",
            is_default=True,
            is_active=True,
        )
        campus_stage = self.make_stage(grading_scale=scale)
        campus_stage.full_clean()
        campus_stage.save()
        campus_stage.refresh_from_db()

        self.assertEqual(campus_stage.grading_scale, scale)
        self.assertEqual(campus_stage.legacy_grading_scale_id, scale.pk)
        self.assertEqual(campus_stage.grading_scale_name, scale.name)

    def test_inactive_grading_scale_is_rejected(self):
        scale = GradingScale.objects.create(
            name="Inactive Scale",
            is_active=False,
        )
        campus_stage = self.make_stage(grading_scale=scale)

        with self.assertRaises(ValidationError) as error:
            campus_stage.full_clean()

        self.assertIn("grading_scale", error.exception.message_dict)

    def test_custom_report_mode_requires_layout_key(self):
        campus_stage = self.make_stage(
            report_mode=CampusEducationStage.REPORT_CUSTOM,
            report_layout_key="",
        )

        with self.assertRaises(ValidationError) as error:
            campus_stage.full_clean()

        self.assertIn("report_layout_key", error.exception.message_dict)

    def test_readiness_detects_numeric_stage_without_grading_scale(self):
        campus_stage = self.make_stage(
            default_assessment_mode=CampusEducationStage.ASSESSMENT_NUMERIC,
        )
        campus_stage.full_clean()
        campus_stage.save()

        readiness = framework_readiness(self.profile)

        self.assertFalse(readiness["checks"]["grading_required_configured"])
        self.assertEqual(readiness["numeric_without_grading_count"], 1)

    def test_competency_stage_does_not_require_numeric_grading_scale(self):
        campus_stage = self.make_stage(
            default_assessment_mode=CampusEducationStage.ASSESSMENT_COMPETENCY,
            report_mode=CampusEducationStage.REPORT_COMPETENCY,
            supports_promotion_decisions=False,
        )
        campus_stage.full_clean()
        campus_stage.save()

        readiness = framework_readiness(self.profile)

        self.assertTrue(readiness["checks"]["grading_required_configured"])
        self.assertEqual(readiness["numeric_without_grading_count"], 0)
