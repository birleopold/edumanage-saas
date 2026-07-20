from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.tenant.academics.models import Level
from apps.tenant.orgsettings.models import Campus, OrganizationProfile

from .models import InstitutionEducationProfile, LevelStageMapping


class EducationFrameworkCommandTests(TestCase):
    def setUp(self):
        self.organization = OrganizationProfile.objects.create(
            name="Command Test School"
        )
        self.campus = Campus.objects.create(
            organization=self.organization,
            name="Main Campus",
            is_default=True,
            is_active=True,
        )

    def test_bootstrap_rejects_invalid_country_code(self):
        with self.assertRaisesMessage(
            CommandError,
            "--country-code must be a two-letter alphabetic code",
        ):
            call_command(
                "bootstrap_education_frameworks",
                organization_id=self.organization.pk,
                country_code="UGA",
            )

    def test_bootstrap_rejects_missing_organization_id(self):
        with self.assertRaisesMessage(
            CommandError,
            "Organization profile 999999 was not found",
        ):
            call_command(
                "bootstrap_education_frameworks",
                organization_id=999999,
            )

    def test_dry_run_does_not_create_profile_or_mapping(self):
        Level.objects.create(name="P4", order=10)
        output = StringIO()

        call_command(
            "bootstrap_education_frameworks",
            organization_id=self.organization.pk,
            map_levels=True,
            enable_mapped_stages=True,
            dry_run=True,
            stdout=output,
        )

        self.assertFalse(
            InstitutionEducationProfile.objects.filter(
                organization=self.organization
            ).exists()
        )
        self.assertFalse(LevelStageMapping.objects.exists())
        self.assertIn("Dry run complete", output.getvalue())

    def test_bootstrap_is_idempotent_and_preserves_levels(self):
        level = Level.objects.create(name="Senior 4", order=10)
        first_output = StringIO()
        second_output = StringIO()

        call_command(
            "bootstrap_education_frameworks",
            organization_id=self.organization.pk,
            map_levels=True,
            enable_mapped_stages=True,
            stdout=first_output,
        )
        call_command(
            "bootstrap_education_frameworks",
            organization_id=self.organization.pk,
            map_levels=True,
            enable_mapped_stages=True,
            stdout=second_output,
        )

        profile = InstitutionEducationProfile.objects.get(
            organization=self.organization
        )
        self.assertEqual(
            LevelStageMapping.objects.filter(profile=profile).count(),
            1,
        )
        self.assertEqual(Level.objects.get(pk=level.pk).name, "Senior 4")
        self.assertEqual(profile.campus_stages.count(), 1)
        self.assertIn("1 created", first_output.getvalue())
        self.assertIn("1 unchanged", second_output.getvalue())
