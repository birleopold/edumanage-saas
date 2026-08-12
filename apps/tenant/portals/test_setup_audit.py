from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    GradeRange,
    GradingScale,
    Level,
)
from apps.tenant.assessments.models import GradingProfile, ReportRule
from apps.tenant.attendance.models import AttendancePolicy
from apps.tenant.education_frameworks.models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.finance.models import FeeItem
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .experience_views import _apply_school_setup_audit
from .setup_audit import (
    _assessment_audit,
    _attendance_audit,
    _calendar_audit,
    _education_structure_audit,
    _finance_audit,
    _learners_audit,
    _subjects_audit,
    _teachers_audit,
)


def _codes(result, group="blockers"):
    return {row["code"] for row in result[group]}


class SetupAuditFixture(TestCase):
    def setUp(self):
        self.org = OrganizationProfile.objects.create(
            name="Audit School",
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
        self.stage, _ = EducationStage.objects.get_or_create(
            code=EducationStage.PRIMARY,
            defaults={
                "name": "Primary Education",
                "order": 20,
                "default_period_type": EducationStage.PERIOD_TERM,
                "is_active": True,
            },
        )
        if not self.stage.is_active:
            self.stage.is_active = True
            self.stage.save(update_fields=["is_active"])
        self.framework = AcademicFramework.objects.create(
            code="AUDIT-FRAMEWORK",
            name="Audit Framework",
            country_code="UG",
            is_active=True,
        )
        self.framework_stage = FrameworkStage.objects.create(
            framework=self.framework,
            stage=self.stage,
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
            stage=self.stage,
            framework_stage=self.framework_stage,
            academic_period_type=EducationStage.PERIOD_TERM,
            is_active=True,
        )
        self.level = Level.objects.create(name="P1", order=10, is_active=True)
        LevelStageMapping.objects.create(
            profile=self.profile,
            stage=self.stage,
            legacy_level_id=self.level.pk,
            legacy_level_name=self.level.name,
            local_name=self.level.name,
        )
        self.class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="P1",
            level=self.level,
            is_active=True,
        )

    def make_calendar(self):
        year = AcademicYear.objects.create(
            name="2026",
            is_current=True,
        )
        term = AcademicTerm.objects.create(
            year=year,
            name="Term 2",
            type=AcademicTerm.TERM,
            order=2,
            is_current=True,
        )
        return year, term

    def make_offering(self, term, *, teacher=None, course_name="Mathematics"):
        course = Course.objects.create(
            name=course_name,
            code=course_name[:4].upper(),
            level=self.level,
            is_active=True,
        )
        return CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=self.class_group,
            teacher=teacher,
            is_active=True,
        )


class CalendarValidityTests(SetupAuditFixture):
    def test_multiple_current_years_are_not_reported_ready(self):
        AcademicYear.objects.create(name="2025", is_current=True)
        year = AcademicYear.objects.create(name="2026", is_current=True)
        AcademicTerm.objects.create(year=year, name="Term 1", is_current=True)

        result = _calendar_audit(self.profile)

        self.assertIn("multiple_current_years", _codes(result))
        self.assertFalse(result["valid"])
        self.assertIsNone(result["metrics"]["current_year_id"])

    def test_current_term_must_belong_to_current_year(self):
        current_year = AcademicYear.objects.create(name="2026", is_current=True)
        other_year = AcademicYear.objects.create(name="2025", is_current=False)
        AcademicTerm.objects.create(
            year=other_year,
            name="Term 3",
            type=AcademicTerm.TERM,
            is_current=True,
        )

        result = _calendar_audit(self.profile)

        self.assertIn("current_term_wrong_year", _codes(result))
        self.assertEqual(result["metrics"]["current_year_id"], current_year.pk)
        self.assertFalse(result["valid"])


class EducationStructureValidityTests(SetupAuditFixture):
    def test_every_active_campus_needs_an_education_stage(self):
        Campus.objects.create(
            organization=self.org,
            name="Annex",
            code="ANNEX",
            is_active=True,
        )
        campuses = list(Campus.objects.filter(organization=self.org, is_active=True))

        result = _education_structure_audit(self.org, self.profile, campuses)

        self.assertIn("campus_stage_missing", _codes(result))
        self.assertFalse(result["valid"])

    def test_active_unmapped_level_is_a_blocker(self):
        Level.objects.create(name="P2", order=20, is_active=True)

        result = _education_structure_audit(self.org, self.profile, [self.campus])

        self.assertIn("active_levels_unmapped", _codes(result))
        self.assertFalse(result["valid"])


class SubjectOfferingValidityTests(SetupAuditFixture):
    def test_old_term_offering_does_not_make_current_term_ready(self):
        current_year, current_term = self.make_calendar()
        old_term = AcademicTerm.objects.create(
            year=current_year,
            name="Term 1",
            type=AcademicTerm.TERM,
            order=1,
            is_current=False,
        )
        self.make_offering(old_term)

        result = _subjects_audit(self.profile, [self.campus], current_term.pk)

        self.assertIn("current_offerings_missing", _codes(result))
        self.assertEqual(result["metrics"]["current_offering_count"], 0)
        self.assertFalse(result["valid"])

    def test_every_active_school_class_needs_current_subjects(self):
        _year, term = self.make_calendar()
        self.make_offering(term)
        p2 = Level.objects.create(name="P2", order=20, is_active=True)
        LevelStageMapping.objects.create(
            profile=self.profile,
            stage=self.stage,
            legacy_level_id=p2.pk,
            legacy_level_name=p2.name,
        )
        ClassGroup.objects.create(
            campus=self.campus,
            name="P2",
            level=p2,
            is_active=True,
        )

        result = _subjects_audit(self.profile, [self.campus], term.pk)

        self.assertIn("class_without_current_subjects", _codes(result))
        self.assertFalse(result["valid"])


class AssessmentValidityTests(SetupAuditFixture):
    def _profile_with_scale(self, scale):
        profile = GradingProfile.objects.create(
            code="DEFAULT-GRADE",
            name="Default Grading",
            grading_scale=scale,
            is_default=True,
            is_active=True,
        )
        ReportRule.objects.create(grading_profile=profile)
        return profile

    def test_empty_grading_scale_is_not_ready(self):
        scale = GradingScale.objects.create(name="Empty Scale", is_active=True)
        self._profile_with_scale(scale)

        result = _assessment_audit()

        self.assertIn("grading_scale_empty", _codes(result))
        self.assertFalse(result["valid"])

    def test_overlapping_grade_ranges_are_blocked(self):
        scale = GradingScale.objects.create(name="Overlap Scale", is_active=True)
        GradeRange.objects.create(scale=scale, grade="F", min_score=0, max_score=60, order=2)
        GradeRange.objects.create(scale=scale, grade="A", min_score=50, max_score=100, order=1)
        self._profile_with_scale(scale)

        result = _assessment_audit()

        self.assertIn("grading_ranges_invalid", _codes(result))
        self.assertFalse(result["valid"])


class TeacherAssignmentValidityTests(SetupAuditFixture):
    def test_inactive_teacher_does_not_count_as_assigned(self):
        _year, term = self.make_calendar()
        teacher = TeacherProfile.objects.create(
            campus=self.campus,
            staff_id="T-1",
            first_name="Inactive",
            last_name="Teacher",
            is_active=False,
        )
        self.make_offering(term, teacher=teacher)

        result = _teachers_audit([self.campus], term.pk)

        self.assertIn("teachers_missing", _codes(result))
        self.assertIn("offering_teacher_missing", _codes(result))
        self.assertEqual(result["metrics"]["assigned_offering_count"], 0)
        self.assertFalse(result["valid"])


class LearnerPlacementValidityTests(SetupAuditFixture):
    def test_existing_learner_without_placement_is_not_go_live_ready(self):
        _year, term = self.make_calendar()
        StudentProfile.objects.create(
            campus=self.campus,
            student_id="S-1",
            first_name="Amina",
            last_name="Learner",
            is_active=True,
        )

        result = _learners_audit([self.campus], term.pk)

        self.assertIn("student_not_placed", _codes(result))
        self.assertEqual(result["metrics"]["placed_student_count"], 0)
        self.assertFalse(result["valid"])

    def test_current_enrollment_is_a_valid_placement_without_stream(self):
        _year, term = self.make_calendar()
        student = StudentProfile.objects.create(
            campus=self.campus,
            student_id="S-2",
            first_name="Brian",
            last_name="Learner",
            is_active=True,
        )
        offering = self.make_offering(term)
        Enrollment.objects.create(
            campus=self.campus,
            offering=offering,
            student=student,
            status=Enrollment.ACTIVE,
        )

        result = _learners_audit([self.campus], term.pk)

        self.assertNotIn("student_not_placed", _codes(result))
        self.assertEqual(result["metrics"]["placed_student_count"], 1)

    def test_duplicate_student_ids_are_blocked(self):
        _year, term = self.make_calendar()
        offering = self.make_offering(term)
        for first_name in ("One", "Two"):
            student = StudentProfile.objects.create(
                campus=self.campus,
                student_id="DUP-1",
                first_name=first_name,
                last_name="Learner",
                is_active=True,
            )
            Enrollment.objects.create(
                campus=self.campus,
                offering=offering,
                student=student,
                status=Enrollment.ACTIVE,
            )

        result = _learners_audit([self.campus], term.pk)

        self.assertIn("duplicate_student_ids", _codes(result))
        self.assertFalse(result["valid"])


class OptionalSetupValidityTests(SetupAuditFixture):
    def test_duplicate_default_attendance_policies_are_flagged(self):
        for name in ("Staff Default A", "Staff Default B"):
            AttendancePolicy.objects.create(
                name=name,
                campus=self.campus,
                person_type=AttendancePolicy.STAFF,
                is_default=True,
                is_active=True,
            )

        result = _attendance_audit([self.campus])

        self.assertIn("attendance_multiple_defaults", _codes(result))
        self.assertFalse(result["valid"])

    def test_negative_fee_item_is_flagged_when_finance_is_used(self):
        FeeItem.objects.create(code="BAD", name="Bad Fee", amount=-100, is_active=True)

        result = _finance_audit(self.org)

        self.assertIn("negative_fee_items", _codes(result))
        self.assertFalse(result["valid"])


class SetupProgressAuditApplicationTests(TestCase):
    def test_blocker_removes_false_ready_status_and_recalculates_progress(self):
        progress = {
            "steps": [
                {
                    "key": "calendar",
                    "done": True,
                    "status": "complete",
                    "optional": False,
                    "evidence": ["Current year: 2026", "Current period: Term 2"],
                },
                {
                    "key": "subjects",
                    "done": True,
                    "status": "complete",
                    "optional": False,
                    "evidence": ["3 active subjects", "3 live offerings", "0 pathways"],
                },
            ],
            "operations": [],
            "done_count": 2,
            "remaining_count": 0,
            "total": 2,
            "percent": 100,
            "all_done": True,
            "next_step": None,
        }
        blocker = {
            "code": "current_term_wrong_year",
            "title": "Wrong year",
            "message": "The current term belongs to another year.",
            "action_label": "Fix calendar",
            "action_url_name": "admin_academic_term_list",
        }
        audit = {
            "steps": {
                "calendar": {"valid": False, "blockers": [blocker], "warnings": [], "metrics": {}},
                "subjects": {
                    "valid": True,
                    "blockers": [],
                    "warnings": [],
                    "metrics": {"current_offering_count": 3},
                },
            },
            "blocker_count": 1,
            "warning_count": 0,
            "core_blocker_count": 1,
        }

        _apply_school_setup_audit(progress, audit)

        self.assertFalse(progress["steps"][0]["done"])
        self.assertEqual(progress["steps"][0]["status"], "incomplete")
        self.assertEqual(progress["done_count"], 1)
        self.assertEqual(progress["remaining_count"], 1)
        self.assertEqual(progress["percent"], 50)
        self.assertEqual(progress["next_step"]["key"], "calendar")
