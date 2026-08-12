from django.test import TestCase

from apps.tenant.academics.models import GradeRange, GradingScale, Level
from apps.tenant.assessments.grading_forms import GradingProfileForm
from apps.tenant.attendance.device_forms import AttendancePolicyForm
from apps.tenant.attendance.models import AttendancePolicy
from apps.tenant.education_frameworks.models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.finance.forms import FeeItemForm
from apps.tenant.orgsettings.forms import CampusForm, OrganizationProfileForm
from apps.tenant.orgsettings.models import Campus, OrganizationProfile


class RemainingSetupFormFixture(TestCase):
    def setUp(self):
        self.org = OrganizationProfile.objects.create(
            name="Simple Setup School",
            email="admin@example.com",
            default_currency="UGX",
        )
        self.campus = Campus.objects.create(
            organization=self.org,
            name="Main Campus",
            code="MAIN",
            is_active=True,
            is_default=True,
        )
        self.primary_stage, _ = EducationStage.objects.get_or_create(
            code=EducationStage.PRIMARY,
            defaults={
                "name": "Primary Education",
                "order": 20,
                "default_period_type": EducationStage.PERIOD_TERM,
                "is_active": True,
            },
        )
        if not self.primary_stage.is_active:
            self.primary_stage.is_active = True
            self.primary_stage.save(update_fields=["is_active"])
        self.lower_stage, _ = EducationStage.objects.get_or_create(
            code=EducationStage.LOWER_SECONDARY,
            defaults={
                "name": "Lower Secondary",
                "order": 30,
                "default_period_type": EducationStage.PERIOD_TERM,
                "is_active": True,
            },
        )
        if not self.lower_stage.is_active:
            self.lower_stage.is_active = True
            self.lower_stage.save(update_fields=["is_active"])
        self.framework = AcademicFramework.objects.create(
            code="SIMPLE-SETUP-FRAMEWORK",
            name="Simple Setup Framework",
            country_code="UG",
            is_active=True,
        )
        self.framework_stage = FrameworkStage.objects.create(
            framework=self.framework,
            stage=self.primary_stage,
            local_name="Primary",
            is_active=True,
        )
        self.profile = InstitutionEducationProfile.objects.create(
            organization=self.org,
            institution_type=InstitutionEducationProfile.PRIMARY,
            country_code="UG",
            locale="en-UG",
            primary_framework=self.framework,
        )
        CampusEducationStage.objects.create(
            profile=self.profile,
            campus=self.campus,
            stage=self.primary_stage,
            framework_stage=self.framework_stage,
            academic_period_type=EducationStage.PERIOD_TERM,
            is_active=True,
        )
        self.level = Level.objects.create(name="P1", order=10, is_active=True)
        LevelStageMapping.objects.create(
            profile=self.profile,
            stage=self.primary_stage,
            legacy_level_id=self.level.pk,
            legacy_level_name=self.level.name,
            local_name=self.level.name,
        )
        self.scale = GradingScale.objects.create(
            name="Valid Scale",
            is_default=True,
            is_active=True,
        )
        GradeRange.objects.create(
            scale=self.scale,
            grade="F",
            min_score=0,
            max_score=49.99,
            order=2,
        )
        GradeRange.objects.create(
            scale=self.scale,
            grade="P",
            min_score=50,
            max_score=100,
            order=1,
        )


class InstitutionCampusGuardrailTests(RemainingSetupFormFixture):
    def test_currency_is_normalized_to_uppercase(self):
        form = OrganizationProfileForm(
            data={
                "name": "Simple Setup School",
                "legal_name": "",
                "email": "",
                "phone": "",
                "address": "",
                "default_currency": "usd",
                "primary_color": "",
                "secondary_color": "",
            },
            instance=self.org,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["default_currency"], "USD")

    def test_invalid_currency_code_is_rejected(self):
        form = OrganizationProfileForm(
            data={
                "name": "Simple Setup School",
                "legal_name": "",
                "email": "",
                "phone": "",
                "address": "",
                "default_currency": "12X",
                "primary_color": "",
                "secondary_color": "",
            },
            instance=self.org,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("default_currency", form.errors)

    def test_new_first_active_campus_becomes_default(self):
        self.campus.is_active = False
        self.campus.is_default = False
        self.campus.save(update_fields=["is_active", "is_default"])
        form = CampusForm(
            data={
                "name": "Replacement Campus",
                "code": "rep",
                "email": "",
                "phone": "",
                "address": "",
                "student_number_format": "",
                "is_active": "on",
                "is_default": "",
            },
            organization=self.org,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data["is_default"])
        self.assertEqual(form.cleaned_data["code"], "REP")

    def test_last_active_campus_cannot_be_deactivated(self):
        form = CampusForm(
            data={
                "name": self.campus.name,
                "code": self.campus.code,
                "email": "",
                "phone": "",
                "address": "",
                "student_number_format": "",
                "is_active": "",
                "is_default": "",
            },
            instance=self.campus,
            organization=self.org,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("is_active", form.errors)

    def test_inactive_campus_cannot_be_default(self):
        annex = Campus.objects.create(
            organization=self.org,
            name="Annex",
            code="ANNEX",
            is_active=True,
        )
        form = CampusForm(
            data={
                "name": annex.name,
                "code": annex.code,
                "email": "",
                "phone": "",
                "address": "",
                "student_number_format": "",
                "is_active": "",
                "is_default": "on",
            },
            instance=annex,
            organization=self.org,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("is_active", form.errors)


class GradingProfileScopeGuardrailTests(RemainingSetupFormFixture):
    def _base_data(self):
        return {
            "code": "DEFAULT-GRADING",
            "name": "Default Grading",
            "description": "",
            "grading_scale": self.scale.pk,
            "campus": self.campus.pk,
            "stage": self.primary_stage.pk,
            "level": self.level.pk,
            "program": "",
            "course": "",
            "academic_term": "",
            "overall_aggregation": "MEAN",
            "incomplete_result_policy": "EXCLUDE",
            "pass_percentage": "50",
            "promotion_percentage": "",
            "minimum_passed_courses": "",
            "decimal_places": "2",
            "priority": "0",
            "is_default": "on",
            "is_active": "on",
        }

    def test_create_form_hides_inactive_scope_choices(self):
        inactive_level = Level.objects.create(name="Old P1", order=99, is_active=False)

        form = GradingProfileForm()

        self.assertNotIn(inactive_level, form.fields["level"].queryset)
        self.assertIn(self.level, form.fields["level"].queryset)

    def test_level_and_stage_scope_must_agree(self):
        data = self._base_data()
        data["stage"] = self.lower_stage.pk
        form = GradingProfileForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("stage", form.errors)

    def test_campus_stage_must_be_enabled_before_grading_rule_can_target_it(self):
        data = self._base_data()
        data["stage"] = self.lower_stage.pk
        data["level"] = ""
        form = GradingProfileForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("stage", form.errors)


class AttendancePolicyGuardrailTests(RemainingSetupFormFixture):
    def _data(self, **overrides):
        data = {
            "name": "Staff attendance",
            "campus": self.campus.pk,
            "person_type": AttendancePolicy.STAFF,
            "expected_in": "08:00",
            "expected_out": "17:00",
            "late_grace_minutes": 10,
            "early_departure_grace_minutes": 10,
            "duplicate_window_seconds": 30,
            "minimum_presence_minutes": 0,
            "direction_strategy": AttendancePolicy.FIRST_LAST,
            "weekdays": "[0,1,2,3,4]",
            "notify_parent_on_arrival": "on",
            "notify_parent_on_departure": "on",
            "is_default": "on",
            "is_active": "on",
            "settings": "{}",
        }
        data.update(overrides)
        return data

    def test_invalid_weekday_numbers_are_rejected(self):
        form = AttendancePolicyForm(data=self._data(weekdays="[0,1,7]"))

        self.assertFalse(form.is_valid())
        self.assertIn("weekdays", form.errors)

    def test_staff_policy_ignores_parent_notification_switches(self):
        form = AttendancePolicyForm(data=self._data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["notify_parent_on_arrival"])
        self.assertFalse(form.cleaned_data["notify_parent_on_departure"])

    def test_default_policy_save_clears_previous_default_same_scope(self):
        previous = AttendancePolicy.objects.create(
            name="Old Staff Default",
            campus=self.campus,
            person_type=AttendancePolicy.STAFF,
            is_default=True,
            is_active=True,
        )
        form = AttendancePolicyForm(data=self._data(name="New Staff Default"))

        self.assertTrue(form.is_valid(), form.errors)
        current = form.save()
        previous.refresh_from_db()

        self.assertTrue(current.is_default)
        self.assertFalse(previous.is_default)

    def test_inactive_policy_cannot_be_marked_default(self):
        form = AttendancePolicyForm(
            data=self._data(is_active="", is_default="on")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("is_active", form.errors)


class FinanceSetupGuardrailTests(RemainingSetupFormFixture):
    def test_negative_fee_amount_is_rejected(self):
        form = FeeItemForm(
            data={
                "code": "tuition",
                "name": "Tuition",
                "amount": "-1000",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_fee_code_is_normalized_and_zero_remains_allowed(self):
        form = FeeItemForm(
            data={
                "code": "lunch",
                "name": "Lunch",
                "amount": "0",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["code"], "LUNCH")
