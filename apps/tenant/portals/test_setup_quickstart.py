from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.tenant.education_frameworks.models import InstitutionEducationProfile

from .setup_quickstart import (
    bootstrap_uganda_standard_levels,
    is_uganda_standard_level_quickstart_available,
    sync_existing_education_structure,
    uganda_standard_level_plan,
)


def _profile(institution_type, *, country="UG", framework_code="UG-NATIONAL"):
    return SimpleNamespace(
        country_code=country,
        institution_type=institution_type,
        primary_framework=SimpleNamespace(code=framework_code),
    )


class UgandaStandardLevelPlanTests(SimpleTestCase):
    def test_primary_plan_contains_only_p1_to_p7(self):
        profile = _profile(InstitutionEducationProfile.PRIMARY)

        self.assertTrue(is_uganda_standard_level_quickstart_available(profile))
        self.assertEqual(
            [row["name"] for row in uganda_standard_level_plan(profile)],
            ["P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        )

    def test_secondary_plan_contains_s1_to_s6_in_order(self):
        profile = _profile(InstitutionEducationProfile.SECONDARY)

        self.assertEqual(
            [row["name"] for row in uganda_standard_level_plan(profile)],
            ["S1", "S2", "S3", "S4", "S5", "S6"],
        )

    def test_mixed_plan_contains_primary_then_secondary_levels(self):
        profile = _profile(InstitutionEducationProfile.MIXED)

        self.assertEqual(
            [row["name"] for row in uganda_standard_level_plan(profile)],
            [
                "P1",
                "P2",
                "P3",
                "P4",
                "P5",
                "P6",
                "P7",
                "S1",
                "S2",
                "S3",
                "S4",
                "S5",
                "S6",
            ],
        )

    def test_non_uganda_or_higher_education_profiles_are_not_eligible(self):
        self.assertFalse(
            is_uganda_standard_level_quickstart_available(
                _profile(InstitutionEducationProfile.PRIMARY, country="KE")
            )
        )
        self.assertFalse(
            is_uganda_standard_level_quickstart_available(
                _profile(
                    InstitutionEducationProfile.PRIMARY,
                    framework_code="INTERNATIONAL-CUSTOM",
                )
            )
        )
        self.assertEqual(
            uganda_standard_level_plan(
                _profile(InstitutionEducationProfile.UNIVERSITY)
            ),
            [],
        )


class UgandaStandardLevelMutationTests(TestCase):
    @patch("apps.tenant.portals.setup_quickstart.sync_existing_education_structure")
    @patch("apps.tenant.portals.setup_quickstart.Level.objects.create")
    @patch("apps.tenant.portals.setup_quickstart.Level.objects.filter")
    def test_bootstrap_preserves_existing_inactive_level_and_creates_only_missing(
        self,
        filter_mock,
        create_mock,
        sync_mock,
    ):
        inactive_p1 = SimpleNamespace(name="P1", is_active=False)
        filter_mock.return_value.order_by.return_value.first.side_effect = [
            inactive_p1,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        sync_mock.return_value = {
            "mapping": {"created": 0, "updated": 0, "unchanged": 0, "manual_preserved": 0},
            "campus_stages_created": 0,
            "framework_links": {"updated": 0, "cleared": 0, "unchanged": 0, "unsupported": 0},
        }
        profile = _profile(InstitutionEducationProfile.PRIMARY)

        summary = bootstrap_uganda_standard_levels(profile)

        self.assertEqual(summary["created_levels"], 6)
        self.assertEqual(summary["existing_levels"], 1)
        self.assertEqual(summary["inactive_preserved"], 1)
        self.assertEqual(create_mock.call_count, 6)
        self.assertEqual(
            [call.kwargs["name"] for call in create_mock.call_args_list],
            ["P2", "P3", "P4", "P5", "P6", "P7"],
        )
        sync_mock.assert_called_once_with(profile)

    def test_bootstrap_rejects_ineligible_profile_before_creating_levels(self):
        profile = _profile(InstitutionEducationProfile.UNIVERSITY)

        with self.assertRaisesMessage(ValueError, "Uganda standard-level quick start"):
            bootstrap_uganda_standard_levels(profile)

    @patch("apps.tenant.portals.setup_quickstart.sync_framework_stage_links")
    @patch("apps.tenant.portals.setup_quickstart.enable_mapped_stages")
    @patch("apps.tenant.portals.setup_quickstart.map_existing_levels")
    def test_sync_existing_structure_delegates_to_non_destructive_framework_services(
        self,
        map_mock,
        enable_mock,
        links_mock,
    ):
        profile = _profile(InstitutionEducationProfile.SECONDARY)
        map_mock.return_value = {
            "created": 3,
            "updated": 1,
            "unchanged": 2,
            "manual_preserved": 1,
        }
        enable_mock.return_value = 2
        links_mock.return_value = {
            "updated": 2,
            "cleared": 0,
            "unchanged": 1,
            "unsupported": 0,
        }

        summary = sync_existing_education_structure(profile)

        map_mock.assert_called_once_with(profile)
        enable_mock.assert_called_once_with(profile)
        links_mock.assert_called_once_with(profile)
        self.assertEqual(summary["campus_stages_created"], 2)
        self.assertEqual(summary["mapping"]["manual_preserved"], 1)
