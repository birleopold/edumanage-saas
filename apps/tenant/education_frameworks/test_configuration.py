from django.test import TestCase

from apps.tenant.academics.models import ClassGroup, Level
from apps.tenant.orgsettings.models import Campus, OrganizationProfile

from .configuration import (
    framework_readiness,
    resolve_effective_terminology,
    sync_framework_stage_links,
)
from .models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
)
from .services import (
    enable_mapped_stages,
    ensure_institution_profile,
    ensure_system_templates,
    map_existing_levels,
)


class EducationFrameworkConfigurationTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(
            name="Configuration Test School"
        )
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
        self.profile.save(
            update_fields=[
                "use_local_terminology",
                "terminology",
                "updated_at",
            ]
        )
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
        self.assertEqual(
            terminology["education_stage"],
            "Primary Education",
        )

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
        self.profile.primary_framework = self.frameworks[
            "INTERNATIONAL-CUSTOM"
        ]
        self.profile.save(
            update_fields=["primary_framework", "updated_at"]
        )

        summary = sync_framework_stage_links(self.profile)
        campus_stage.refresh_from_db()

        self.assertEqual(summary["updated"], 1)
        self.assertEqual(
            campus_stage.framework_stage.framework,
            self.frameworks["INTERNATIONAL-CUSTOM"],
        )
        self.assertEqual(campus_stage.local_name, "Lower Primary")
        self.assertEqual(
            campus_stage.report_layout_key,
            "custom-primary-report",
        )

    def test_unsupported_stage_clears_only_the_old_framework_link(self):
        primary = self.stages[EducationStage.PRIMARY]
        campus_stage = CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary,
            framework_stage=FrameworkStage.objects.get(
                framework=self.frameworks["UG-NATIONAL"],
                stage=primary,
            ),
            local_name="Primary Section",
            report_layout_key="school-primary",
            academic_period_type=EducationStage.PERIOD_TERM,
        )
        custom_framework = AcademicFramework.objects.create(
            code="CUSTOM-WITHOUT-PRIMARY",
            name="Custom Limited Framework",
            is_active=True,
        )
        self.profile.primary_framework = custom_framework
        self.profile.save(
            update_fields=["primary_framework", "updated_at"]
        )

        summary = sync_framework_stage_links(self.profile)
        campus_stage.refresh_from_db()

        self.assertEqual(summary["unsupported"], 1)
        self.assertEqual(summary["cleared"], 1)
        self.assertIsNone(campus_stage.framework_stage)
        self.assertEqual(campus_stage.local_name, "Primary Section")
        self.assertEqual(
            campus_stage.report_layout_key,
            "school-primary",
        )
        readiness = framework_readiness(self.profile)
        self.assertFalse(readiness["checks"]["stages_supported"])
        self.assertEqual(readiness["unsupported_stage_link_count"], 1)

    def test_readiness_reports_unmapped_levels_without_mutating_them(self):
        level = Level.objects.create(name="P4", order=10)

        before = framework_readiness(self.profile)
        map_existing_levels(self.profile)
        after = framework_readiness(self.profile)

        self.assertEqual(before["unmapped_level_count"], 1)
        self.assertEqual(after["unmapped_level_count"], 0)
        self.assertEqual(Level.objects.get(pk=level.pk).name, "P4")

    def test_single_campus_requires_every_mapped_stage(self):
        Level.objects.create(name="P4", order=10)
        Level.objects.create(name="Senior 2", order=20)
        map_existing_levels(self.profile)
        primary = self.stages[EducationStage.PRIMARY]
        CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary,
            framework_stage=FrameworkStage.objects.get(
                framework=self.frameworks["UG-NATIONAL"],
                stage=primary,
            ),
            academic_period_type=EducationStage.PERIOD_TERM,
        )

        before = framework_readiness(self.profile)
        enable_mapped_stages(self.profile)
        after = framework_readiness(self.profile)

        self.assertFalse(before["checks"]["campuses_configured"])
        self.assertEqual(before["missing_campus_stage_count"], 1)
        self.assertTrue(after["checks"]["campuses_configured"])
        self.assertEqual(after["missing_campus_stage_count"], 0)

    def test_multi_campus_stage_enablement_follows_each_campus_classes(self):
        secondary_campus = Campus.objects.create(
            organization=self.organization,
            name="Secondary Campus",
            is_active=True,
        )
        primary_level = Level.objects.create(name="P4", order=10)
        secondary_level = Level.objects.create(name="Senior 2", order=20)
        ClassGroup.objects.create(
            campus=self.campus,
            name="P4 Blue",
            level=primary_level,
            is_active=True,
        )
        ClassGroup.objects.create(
            campus=secondary_campus,
            name="S2 East",
            level=secondary_level,
            is_active=True,
        )
        map_existing_levels(self.profile)

        created = enable_mapped_stages(self.profile)
        readiness = framework_readiness(self.profile)

        self.assertEqual(created, 2)
        self.assertSetEqual(
            set(
                self.profile.campus_stages.filter(
                    campus=self.campus
                ).values_list("stage__code", flat=True)
            ),
            {EducationStage.PRIMARY},
        )
        self.assertSetEqual(
            set(
                self.profile.campus_stages.filter(
                    campus=secondary_campus
                ).values_list("stage__code", flat=True)
            ),
            {EducationStage.LOWER_SECONDARY},
        )
        self.assertTrue(readiness["checks"]["campuses_configured"])
        self.assertEqual(readiness["unassigned_campus_count"], 0)

    def test_multi_campus_without_class_evidence_requires_manual_assignment(self):
        Campus.objects.create(
            organization=self.organization,
            name="New Campus",
            is_active=True,
        )
        Level.objects.create(name="P4", order=10)
        map_existing_levels(self.profile)
        enable_mapped_stages(self.profile)

        readiness = framework_readiness(self.profile)

        self.assertFalse(readiness["checks"]["campuses_configured"])
        self.assertEqual(readiness["unassigned_campus_count"], 2)
        self.assertEqual(self.profile.campus_stages.count(), 0)

    def test_readiness_detects_wrong_framework_and_stage_links(self):
        primary = self.stages[EducationStage.PRIMARY]
        lower_secondary = self.stages[EducationStage.LOWER_SECONDARY]
        CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary,
            framework_stage=FrameworkStage.objects.get(
                framework=self.frameworks["INTERNATIONAL-CUSTOM"],
                stage=lower_secondary,
            ),
            academic_period_type=EducationStage.PERIOD_TERM,
        )

        readiness = framework_readiness(self.profile)

        self.assertFalse(readiness["checks"]["framework_links_valid"])
        self.assertFalse(readiness["checks"]["stage_links_valid"])
        self.assertEqual(readiness["framework_mismatch_count"], 1)
        self.assertEqual(readiness["stage_mismatch_count"], 1)
