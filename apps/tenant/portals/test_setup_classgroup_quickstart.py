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


def _single_campus(campus_filter, name="Main Campus"):
    campus = SimpleNamespace(pk=1, name=name)
    campus_filter.return_value.order_by.return_value.__getitem__.return_value = [
        campus
    ]
    return campus


def _active_level_queryset(level_filter, scoped_levels, out_of_scope_names=()):
    active_qs = MagicMock()
    level_filter.return_value = active_qs
    active_qs.filter.return_value.order_by.return_value.__iter__.return_value = iter(
        scoped_levels
    )
    active_qs.exclude.return_value.order_by.return_value.values_list.return_value = list(
        out_of_scope_names
    )
    return active_qs


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

    @patch("apps.tenant.portals.setup_quickstart._campus_stage_ids", return_value=set())
    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_single_campus_without_enabled_stages_cannot_auto_create_classes(
        self,
        campus_filter,
        _stage_ids,
    ):
        _single_campus(campus_filter)

        plan = class_group_quickstart_plan(_profile())

        self.assertFalse(plan["available"])
        self.assertEqual(plan["reason"], "no_enabled_stages")

    @patch("apps.tenant.portals.setup_quickstart._classgroup_name_conflicts")
    @patch("apps.tenant.portals.setup_quickstart._classgroup_candidates_for_level")
    @patch("apps.tenant.portals.setup_quickstart.Level.objects.filter")
    @patch(
        "apps.tenant.portals.setup_quickstart._mapped_level_ids_for_stages",
        return_value={11, 12},
    )
    @patch("apps.tenant.portals.setup_quickstart._campus_stage_ids", return_value={101})
    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_single_campus_plan_only_contains_mapped_in_scope_levels_without_groups(
        self,
        campus_filter,
        _stage_ids,
        _mapped_ids,
        level_filter,
        candidate_helper,
        conflict_helper,
    ):
        _single_campus(campus_filter)
        p1 = SimpleNamespace(pk=11, name="P1", is_active=True)
        p2 = SimpleNamespace(pk=12, name="P2", is_active=True)
        existing_p1 = SimpleNamespace(pk=21, is_active=True)
        _active_level_queryset(level_filter, [p1, p2])
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
    @patch(
        "apps.tenant.portals.setup_quickstart._mapped_level_ids_for_stages",
        return_value={11},
    )
    @patch("apps.tenant.portals.setup_quickstart._campus_stage_ids", return_value={101})
    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_active_unmapped_or_out_of_stage_levels_are_not_offered_for_creation(
        self,
        campus_filter,
        _stage_ids,
        _mapped_ids,
        level_filter,
        candidate_helper,
        conflict_helper,
    ):
        _single_campus(campus_filter)
        p1 = SimpleNamespace(pk=11, name="P1", is_active=True)
        _active_level_queryset(
            level_filter,
            [p1],
            out_of_scope_names=["Year 1", "Custom Level"],
        )
        candidate_helper.return_value.order_by.return_value.first.return_value = None
        conflict_helper.return_value.order_by.return_value.first.return_value = None

        plan = class_group_quickstart_plan(_profile())

        self.assertTrue(plan["available"])
        self.assertEqual(
            [row["level_name"] for row in plan["creatable"]],
            ["P1"],
        )
        self.assertEqual(
            plan["out_of_scope_level_names"],
            ["Year 1", "Custom Level"],
        )

    @patch("apps.tenant.portals.setup_quickstart._classgroup_name_conflicts")
    @patch("apps.tenant.portals.setup_quickstart._classgroup_candidates_for_level")
    @patch("apps.tenant.portals.setup_quickstart.Level.objects.filter")
    @patch(
        "apps.tenant.portals.setup_quickstart._mapped_level_ids_for_stages",
        return_value={11, 12},
    )
    @patch("apps.tenant.portals.setup_quickstart._campus_stage_ids", return_value={101})
    @patch("apps.tenant.portals.setup_quickstart.Campus.objects.filter")
    def test_inactive_and_name_conflicting_groups_are_preserved_for_review(
        self,
        campus_filter,
        _stage_ids,
        _mapped_ids,
        level_filter,
        candidate_helper,
        conflict_helper,
    ):
        _single_campus(campus_filter)
        p1 = SimpleNamespace(pk=11, name="P1", is_active=True)
        p2 = SimpleNamespace(pk=12, name="P2", is_active=True)
        inactive = SimpleNamespace(pk=21, is_active=False)
        conflict = SimpleNamespace(pk=31, is_active=True)
        _active_level_queryset(level_filter, [p1, p2])
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
    @patch("apps.tenant.portals.setup_quickstart._level_is_in_campus_scope")
    @patch("apps.tenant.portals.setup_quickstart.class_group_quickstart_plan")
    def test_bootstrap_creates_only_rows_still_safe_at_write_time(
        self,
        plan_mock,
        scope_helper,
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
            "out_of_scope_level_names": [],
        }
        scope_helper.side_effect = [True, True]
        candidate_helper.return_value.exists.side_effect = [False, True]
        conflict_helper.return_value.exists.return_value = False

        summary = bootstrap_class_groups_from_levels(_profile())

        self.assertEqual(summary["created_count"], 1)
        self.assertEqual(summary["created_names"], ["P1"])
        self.assertEqual(summary["skipped_during_create"], ["P2"])
        self.assertEqual(summary["skipped_out_of_scope"], [])
        create_mock.assert_called_once_with(
            campus=campus,
            level=p1,
            name="P1",
            code="",
            is_active=True,
        )

    @patch("apps.tenant.portals.setup_quickstart.ClassGroup.objects.create")
    @patch("apps.tenant.portals.setup_quickstart._level_is_in_campus_scope")
    @patch("apps.tenant.portals.setup_quickstart.class_group_quickstart_plan")
    def test_bootstrap_rechecks_scope_and_skips_level_if_stage_mapping_changed(
        self,
        plan_mock,
        scope_helper,
        create_mock,
    ):
        campus = SimpleNamespace(pk=1, name="Main Campus")
        p1 = SimpleNamespace(pk=11, name="P1")
        plan_mock.return_value = {
            "available": True,
            "campus": campus,
            "campus_name": campus.name,
            "creatable": [
                {"level": p1, "level_name": "P1", "class_name": "P1"},
            ],
        }
        scope_helper.return_value = False

        summary = bootstrap_class_groups_from_levels(_profile())

        self.assertEqual(summary["created_count"], 0)
        self.assertEqual(summary["skipped_out_of_scope"], ["P1"])
        create_mock.assert_not_called()

    @patch("apps.tenant.portals.setup_quickstart.class_group_quickstart_plan")
    def test_bootstrap_refuses_when_plan_is_ambiguous(self, plan_mock):
        plan_mock.return_value = {
            "available": False,
            "message": "Choose classes per campus manually.",
        }

        with self.assertRaisesMessage(ValueError, "Choose classes per campus manually"):
            bootstrap_class_groups_from_levels(_profile())
