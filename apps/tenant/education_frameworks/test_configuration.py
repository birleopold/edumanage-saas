from django.test import TestCase

from apps.tenant.academics.models import Level
from apps.tenant.orgsettings.models import Campus, OrganizationProfile

from .configuration import (
    framework_readiness,
    resolve_effective_terminology,
    sync_framework_stage_links,
)
from .models import CampusEducationStage, EducationStage, FrameworkStage
from .services import ensure_institution_profile, ensure_system_templates, map_existing_levels


class EducationFrameworkConfigurationTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Configuration Test School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )
        self.stages, self.frameworks = ensure_system_templates()
        self.profile = ensure_institution_profile(self.organization)

    def test_international_neutral_mode_skips_uganda_specific_labels(self):
        self.profile.use_local_terminology = False
        self.profile.terminology = {"learner": "Pupil"}
        self.profile.save(update_fields=["use_local_terminology", "terminology", "updated_at"])
        primary = self.stages[EducationStage.PRIMARY]
        campus_stage = CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary,
            framework_stage=FrameworkStage.objects.get(
                framework=self.frameworks["UG-NATIONAL"],
                stage=primary,
            ),
            local_name="Primary",
            academic_period_type=EducationStage.PERIOD_TERM,
        )

        terminology = resolve_effective_terminology(
            profile=self.profile,
            campus_stage=campus_stage,
        )

        self.assertEqual(terminology["learner"], "Pupil")
        self.assertEqual(terminology["external_exam"], "External Exam")
        self.assertEqual(terminology["education_stage"], "Primary Education")

    def test_framework_link_sync_preserves_local_stage_settings(self):
        primary = self.stages[EducationStage.PRIMARY]
        uganda_stage = FrameworkStage.objects.get(
            framework=self.frameworks["UG-NATIONAL"],
            stage=primary,
        )
        campus_stage = CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary,
            framework_stage=uganda_stage,
            local_name="Lower Primary",
            report_layout_key="custom-primary-report",
            academic_period_type=EducationStage.PERIOD_TERM,
        )
        self.profile.primary_framework = self.frameworks["INTERNATIONAL-CUSTOM"]
        self.profile.save(update_fields=["primary_framework", "updated_at"])

        summary = sync_framework_stage_links(self.profile)
        campus_stage.refresh_from_db()

        self.assertEqual(summary["updated"], 1)
        self.assertEqual(
            campus_stage.framework_stage.framework,
            self.frameworks["INTERNATIONAL-CUSTOM"],
        )
        self.assertEqual(campus_stage.local_name, "Lower Primary")
        self.assertEqual(campus_stage.report_layout_key, "custom-primary-report")

    def test_readiness_reports_unmapped_levels_without_mutating_them(self):
        level = Level.objects.create(name="P4", order=10)

        before = framework_readiness(self.profile)
        map_existing_levels(self.profile)
        after = framework_readiness(self.profile)

        self.assertEqual(before["unmapped_level_count"], 1)
        self.assertEqual(after["unmapped_level_count"], 0)
        self.assertEqual(Level.objects.get(pk=level.pk).name, "P4")
