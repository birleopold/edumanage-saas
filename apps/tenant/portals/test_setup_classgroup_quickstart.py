from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from apps.tenant.education_frameworks.models import InstitutionEducationProfile

from .setup_quickstart import (
    bootstrap_class_groups_from_levels,
    class_group_quickstart_plan,
)


def _profile(institution_type=InstitutionEducationProfile.PRIMARY):
    return SimpleNamespace(
        institution_type=institution_type,
        organization=SimpleNamespace(pk=1),
    )


class ClassGroupQuickStartPlanTests(SimpleTestCase):
    def test_higher_education_is_not_auto_grouped(self):
        plan = class_group_quickstart_plan(
            _profile(InstitutionEducationProfile.UNIVERSITY)
        )

        self.assertFalse(plan["available"])
        self.assertEqual(plan["reason"], "institution_type")

    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_multiple_campuses_are_left_for_explicit_admin_setup(self, campus_filter):
        campus_filter.return_value.order_by.return_value.__getitem__.return_value = [
            SimpleNamespace(pk=1, name="Main"),
            SimpleNamespace(pk=2, name="Annex"),
        ]

        plan = class_group_quickstart_plan(_profile())

        self.assertFalse(plan["available"])
        self.assertEqual(plan["reason"], "multiple_campuses")

    @patch("apps.tenant.portals.setup_quickstart._classgroup_name_conflicts")
    @patch("apps.tenant.portals.setup_quickstart._classgroup_candidates_for_level")
    @patch("apps.tenant.portals.setup_quickstart.Level.objects.filter")
    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_single_campus_plan_only_contains_levels_without_existing_groups(
        self,
        campus_filter,
        level_filter,
        candidate_helper,
        conflict_helper,
    ):
        campus = SimpleNamespace(pk=1, name="Main Campus")
        p1 = SimpleNamespace(pk=11, name="P1", is_active=True)
        p2 = SimpleNamespace(pk=12, name="P2", is_active=True)
        existing_p1 = SimpleNamespace(pk=21, is_active=True)

        campus_filter.return_value.order_by.return_value.__getitem__.return_value = [
            campus
        ]
        level_filter.return_value.order_by.return_value.__iter__.return_value = iter(
            [p1, p2]
        )
        candidate_helper.return_value.order_by.return_value.first.side_effect = [
            existing_p1,
            None,
        ]
        conflict_helper.return_value.order_by.return_value.first.return_value = None

        plan = class_group_quickstart_plan(_profile())

        self.assertTrue(plan["available"])
        self.assertEqual(plan["campus_name"], "Main Campus")
        self.assertEqual(plan["ready_level_names"], ["P1"])
        self.assertEqual(
            [row["level_name"] for row in plan["creatable"]],
            ["P2"],
        )

    @patch("apps.tenant.portals.setup_quickstart._classgroup_name_conflicts")
    @patch("apps.tenant.portals.setup_quickstart._classgroup_candidates_for_level")
    @patch("apps.tenant.portals.setup_quickstart.Level.objects.filter")
    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_inactive_and_name_conflicting_groups_are_preserved_for_review(
        self,
        campus_filter,
        level_filter,
        candidate_helper,
        conflict_helper,
    ):
        campus = SimpleNamespace(pk=1, name="Main Campus")
        p1 = SimpleNamespace(pk=11, name="P1", is_active=True)
        p2 = SimpleNamespace(pk=12, name="P2", is_active=True)
        inactive = SimpleNamespace(pk=21, is_active=False)
        conflict = SimpleNamespace(pk=31, is_active=True)

        campus_filter.return_value.order_by.return_value.__getitem__.return_value = [
            campus
        ]
        level_filter.return_value.order_by.return_value.__iter__.return_value = iter(
            [p1, p2]
        )
        candidate_helper.return_value.order_by.return_value.first.side_effect = [
            inactive,
            None,
        ]
        conflict_helper.return_value.order_by.return_value.first.return_value = conflict

        plan = class_group_quickstart_plan(_profile())

        self.assertFalse(plan["available"])
        self.assertEqual(plan["inactive_level_names"], ["P1"])
        self.assertEqual(plan["conflict_level_names"], ["P2"])
        self.assertEqual(plan["creatable"], [])


class ClassGroupQuickStartMutationTests(TestCase):
    @patch("apps.tenant.portals.setup_quickstart.ClassGroup.objects.create")
    @patch("apps.tenant.portals.setup_quickstart._classgroup_name_conflicts")
    @patch("apps.tenant.portals.setup_quickstart._classgroup_candidates_for_level")
    @patch("apps.tenant.portals.setup_quickstart.class_group_quickstart_plan")
    def test_bootstrap_creates_only_rows_still_safe_at_write_time(
        self,
        plan_mock,
        candidate_helper,
        conflict_helper,
        create_mock,
    ):
        campus = SimpleNamespace(pk=1, name="Main Campus")
        p1 = SimpleNamespace(pk=11, name="P1")
        p2 = SimpleNamespace(pk=12, name="P2")
        plan_mock.return_value = {
            "available": True,
            "campus": campus,
            "campus_name": campus.name,
            "creatable": [
                {"level": p1, "level_name": "P1", "class_name": "P1"},
                {"level": p2, "level_name": "P2", "class_name": "P2"},
            ],
            "inactive_level_names": [],
            "conflict_level_names": [],
        }
        candidate_helper.return_value.exists.side_effect = [False, True]
        conflict_helper.return_value.exists.return_value = False

        summary = bootstrap_class_groups_from_levels(_profile())

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(summary["created_names"], ["P1"])
        self.assertEqual(summary["skipped_during_create"], ["P2"])
        create_mock.assert_called_once_with(
            campus=campus,
            level=p1,
            name="P1",
            code="",
            is_active=True,
        )

    @patch("apps.tenant.portals.setup_quickstart.class_group_quickstart_plan")
    def test_bootstrap_refuses_when_plan_is_ambiguous(self, plan_mock):
        plan_mock.return_value = {
            "available": False,
            "message": "Choose classes per campus manually.",
        }

        with self.assertRaisesMessage(ValueError, "Choose classes per campus manually"):
            bootstrap_class_groups_from_levels(_profile())
