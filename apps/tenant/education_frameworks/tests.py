from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant.academics.models import Level
from apps.tenant.orgsettings.models import Campus, OrganizationProfile

from .models import CampusEducationStage, EducationStage, FrameworkStage, LevelStageMapping
from .services import (
    enable_mapped_stages,
    ensure_institution_profile,
    ensure_system_templates,
    infer_stage_code,
    map_existing_levels,
    resolve_level_stage,
    resolve_terminology,
)


class EducationFrameworkServiceTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(name="Framework Test School")
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            code="MAIN",
            is_default=True,
            is_active=True,
        )
        self.stages, self.frameworks = ensure_system_templates()
        self.profile = ensure_institution_profile(self.organization)

    def test_system_templates_are_idempotent(self):
        ensure_system_templates()
        ensure_system_templates()

        self.assertEqual(EducationStage.objects.filter(is_system=True).count(), 7)
        self.assertEqual(self.frameworks["UG-NATIONAL"].stage_settings.count(), 7)
        self.assertEqual(self.frameworks["INTERNATIONAL-CUSTOM"].stage_settings.count(), 7)

    def test_stage_inference_supports_ugandan_and_international_names(self):
        examples = {
            "Baby Class": EducationStage.ECD,
            "P7": EducationStage.PRIMARY,
            "Grade 6": EducationStage.PRIMARY,
            "Senior 4 O-Level": EducationStage.LOWER_SECONDARY,
            "Grade 10": EducationStage.LOWER_SECONDARY,
            "S6 A-Level": EducationStage.UPPER_SECONDARY,
            "Grade 12": EducationStage.UPPER_SECONDARY,
            "Diploma Year 1": EducationStage.TERTIARY,
            "Bachelor of Education": EducationStage.UNIVERSITY,
            "Community Programme": EducationStage.OTHER,
        }
        for name, expected in examples.items():
            with self.subTest(name=name):
                self.assertEqual(infer_stage_code(name), expected)

    def test_existing_levels_are_mapped_without_being_modified(self):
        primary = Level.objects.create(name="P5", order=10)
        secondary = Level.objects.create(name="Senior 4", order=20)
        tertiary = Level.objects.create(name="Diploma Year 1", order=30)

        summary = map_existing_levels(self.profile)

        self.assertEqual(summary["created"], 3)
        self.assertEqual(Level.objects.get(pk=primary.pk).name, "P5")
        self.assertEqual(Level.objects.get(pk=secondary.pk).name, "Senior 4")
        self.assertEqual(Level.objects.get(pk=tertiary.pk).name, "Diploma Year 1")
        self.assertEqual(resolve_level_stage(primary, self.profile).code, EducationStage.PRIMARY)
        self.assertEqual(resolve_level_stage(secondary, self.profile).code, EducationStage.LOWER_SECONDARY)
        self.assertEqual(resolve_level_stage(tertiary, self.profile).code, EducationStage.TERTIARY)
        self.assertEqual(LevelStageMapping.objects.filter(profile=self.profile).count(), 3)

    def test_mapped_stages_can_be_enabled_per_campus(self):
        Level.objects.create(name="P1", order=10)
        Level.objects.create(name="S1", order=20)
        map_existing_levels(self.profile)

        created = enable_mapped_stages(self.profile)

        self.assertEqual(created, 2)
        self.assertSetEqual(
            set(self.campus.education_stages.values_list("stage__code", flat=True)),
            {EducationStage.PRIMARY, EducationStage.LOWER_SECONDARY},
        )

    def test_terminology_combines_neutral_uganda_and_local_labels(self):
        primary_stage = self.stages[EducationStage.PRIMARY]
        framework_stage = FrameworkStage.objects.get(
            framework=self.frameworks["UG-NATIONAL"],
            stage=primary_stage,
        )
        campus_stage = CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=primary_stage,
            framework_stage=framework_stage,
            local_name="Lower Primary",
            terminology={"exam": "Examination"},
        )
        self.profile.terminology = {"learner": "Pupil"}
        self.profile.save(update_fields=["terminology", "updated_at"])

        terminology = resolve_terminology(profile=self.profile, campus_stage=campus_stage)

        self.assertEqual(terminology["learner"], "Pupil")
        self.assertEqual(terminology["subject"], "Subject")
        self.assertEqual(terminology["exam"], "Examination")
        self.assertEqual(terminology["education_stage"], "Lower Primary")

    def test_campus_stage_rejects_a_campus_from_another_organization(self):
        other_organization = OrganizationProfile.objects.create(name="Other Institution")
        other_campus = Campus.objects.create(
            organization=other_organization,
            name="Other Campus",
            is_active=True,
        )
        campus_stage = CampusEducationStage(
            profile=self.profile,
            campus=other_campus,
            stage=self.stages[EducationStage.PRIMARY],
        )

        with self.assertRaises(ValidationError):
            campus_stage.full_clean()
