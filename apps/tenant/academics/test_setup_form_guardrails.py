from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.tenant.education_frameworks.models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.orgsettings.models import Campus, OrganizationProfile
from apps.tenant.students.forms import StudentProfileForm
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.forms import TeacherProfileForm
from apps.tenant.teachers.models import TeacherProfile

from .forms import (
    AcademicTermForm,
    AcademicYearForm,
    ClassGroupForm,
    CourseOfferingForm,
    GradeRangeForm,
    StreamForm,
)
from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    GradeRange,
    GradingScale,
    Level,
    Stream,
)


class SetupFormFixture(TestCase):
    def setUp(self):
        self.org = OrganizationProfile.objects.create(
            name="Guardrail School",
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
        self.framework = AcademicFramework.objects.create(
            code="FORM-GUARDRAIL-FRAMEWORK",
            name="Form Guardrail Framework",
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
        self.level = Level.objects.create(name="P1", order=10, is_active=True)

    def enable_primary_mapping(self):
        LevelStageMapping.objects.get_or_create(
            profile=self.profile,
            legacy_level_id=self.level.pk,
            defaults={
                "stage": self.primary_stage,
                "legacy_level_name": self.level.name,
                "local_name": self.level.name,
            },
        )
        CampusEducationStage.objects.get_or_create(
            profile=self.profile,
            campus=self.campus,
            stage=self.primary_stage,
            defaults={
                "framework_stage": self.framework_stage,
                "academic_period_type": EducationStage.PERIOD_TERM,
                "is_active": True,
            },
        )


class CalendarFormGuardrailTests(SetupFormFixture):
    def test_saving_current_year_automatically_clears_previous_current_year(self):
        old = AcademicYear.objects.create(name="2025", is_current=True)
        form = AcademicYearForm(
            data={
                "name": "2026",
                "start_date": "",
                "end_date": "",
                "is_current": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        current = form.save()
        old.refresh_from_db()

        self.assertTrue(current.is_current)
        self.assertFalse(old.is_current)
        self.assertEqual(AcademicYear.objects.filter(is_current=True).count(), 1)

    def test_saving_current_term_also_synchronizes_current_year(self):
        old_year = AcademicYear.objects.create(name="2025", is_current=True)
        new_year = AcademicYear.objects.create(name="2026", is_current=False)
        old_term = AcademicTerm.objects.create(
            year=old_year,
            name="Term 3",
            type=AcademicTerm.TERM,
            order=3,
            is_current=True,
        )
        form = AcademicTermForm(
            data={
                "year": new_year.pk,
                "name": "Term 1",
                "type": AcademicTerm.TERM,
                "order": 1,
                "start_date": "",
                "end_date": "",
                "is_current": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        current_term = form.save()
        old_year.refresh_from_db()
        new_year.refresh_from_db()
        old_term.refresh_from_db()

        self.assertTrue(current_term.is_current)
        self.assertTrue(new_year.is_current)
        self.assertFalse(old_year.is_current)
        self.assertFalse(old_term.is_current)
        self.assertEqual(AcademicTerm.objects.filter(is_current=True).count(), 1)

    def test_reversed_academic_year_dates_are_rejected(self):
        form = AcademicYearForm(
            data={
                "name": "2026",
                "start_date": "2026-12-01",
                "end_date": "2026-01-01",
                "is_current": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_term_dates_must_stay_inside_selected_academic_year(self):
        year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        form = AcademicTermForm(
            data={
                "year": year.pk,
                "name": "Term 1",
                "type": AcademicTerm.TERM,
                "order": 1,
                "start_date": "2025-12-20",
                "end_date": "2026-03-31",
                "is_current": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("start_date", form.errors)


class ClassAndOfferingFormGuardrailTests(SetupFormFixture):
    def test_school_class_cannot_use_unmapped_level(self):
        form = ClassGroupForm(
            data={
                "campus": self.campus.pk,
                "name": "P1",
                "code": "",
                "level": self.level.pk,
                "program": "",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("level", form.errors)

    def test_school_class_becomes_valid_after_level_and_stage_are_configured(self):
        self.enable_primary_mapping()
        form = ClassGroupForm(
            data={
                "campus": self.campus.pk,
                "name": "P1",
                "code": "",
                "level": self.level.pk,
                "program": "",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_active_class_name_in_same_campus_is_rejected(self):
        self.enable_primary_mapping()
        ClassGroup.objects.create(
            campus=self.campus,
            name="P1",
            level=self.level,
            is_active=True,
        )
        form = ClassGroupForm(
            data={
                "campus": self.campus.pk,
                "name": "p1",
                "code": "",
                "level": self.level.pk,
                "program": "",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_duplicate_active_offering_same_period_and_class_is_rejected(self):
        self.enable_primary_mapping()
        year = AcademicYear.objects.create(name="2026", is_current=True)
        term = AcademicTerm.objects.create(
            year=year,
            name="Term 1",
            type=AcademicTerm.TERM,
            order=1,
            is_current=True,
        )
        class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="P1",
            level=self.level,
            is_active=True,
        )
        course = Course.objects.create(name="Mathematics", code="MATH", is_active=True)
        CourseOffering.objects.create(
            campus=self.campus,
            course=course,
            term=term,
            class_group=class_group,
            is_active=True,
        )
        form = CourseOfferingForm(
            data={
                "campus": self.campus.pk,
                "course": course.pk,
                "term": term.pk,
                "class_group": class_group.pk,
                "teacher": "",
                "is_active": "on",
            },
            campus=self.campus,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_level_specific_subject_cannot_be_offered_to_different_level(self):
        self.enable_primary_mapping()
        p2 = Level.objects.create(name="P2", order=20, is_active=True)
        year = AcademicYear.objects.create(name="2026")
        term = AcademicTerm.objects.create(year=year, name="Term 1", order=1)
        class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="P1",
            level=self.level,
            is_active=True,
        )
        course = Course.objects.create(name="P2 Mathematics", code="P2-MATH", level=p2, is_active=True)
        form = CourseOfferingForm(
            data={
                "campus": self.campus.pk,
                "course": course.pk,
                "term": term.pk,
                "class_group": class_group.pk,
                "teacher": "",
                "is_active": "on",
            },
            campus=self.campus,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("course", form.errors)


class GradingAndStreamFormGuardrailTests(SetupFormFixture):
    def test_overlapping_grade_range_is_rejected_before_save(self):
        scale = GradingScale.objects.create(name="Default", is_active=True)
        GradeRange.objects.create(
            scale=scale,
            grade="A",
            min_score=80,
            max_score=100,
            order=1,
        )
        form = GradeRangeForm(
            data={
                "scale": scale.pk,
                "grade": "B",
                "min_score": 70,
                "max_score": 85,
                "grade_point": "",
                "remark": "",
                "order": 2,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_class_teacher_must_share_class_campus(self):
        self.enable_primary_mapping()
        other_campus = Campus.objects.create(
            organization=self.org,
            name="Annex",
            code="ANNEX",
            is_active=True,
        )
        class_group = ClassGroup.objects.create(
            campus=self.campus,
            name="P1",
            level=self.level,
            is_active=True,
        )
        teacher = TeacherProfile.objects.create(
            campus=other_campus,
            staff_id="T-2",
            first_name="Other",
            last_name="Campus",
            is_active=True,
        )
        form = StreamForm(
            data={
                "class_group": class_group.pk,
                "name": "A",
                "capacity": 40,
                "class_teacher": teacher.pk,
                "room": "",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("class_teacher", form.errors)


class LearnerAndTeacherIdentityGuardrailTests(SetupFormFixture):
    def test_duplicate_active_student_id_is_rejected_case_insensitively(self):
        StudentProfile.objects.create(
            campus=self.campus,
            student_id="ADM-001",
            first_name="Existing",
            last_name="Learner",
            is_active=True,
        )
        form = StudentProfileForm(
            data={
                "campus": self.campus.pk,
                "stream": "",
                "student_id": "adm-001",
                "email": "",
                "first_name": "New",
                "last_name": "Learner",
                "date_of_birth": "",
                "district": "",
                "subcounty": "",
                "parish": "",
                "nin": "",
                "learner_id": "",
                "is_active": "on",
            },
            campus=self.campus,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("student_id", form.errors)

    def test_future_date_of_birth_is_rejected(self):
        future = timezone.localdate() + timedelta(days=1)
        form = StudentProfileForm(
            data={
                "campus": self.campus.pk,
                "stream": "",
                "student_id": "ADM-002",
                "email": "",
                "first_name": "Future",
                "last_name": "Learner",
                "date_of_birth": future.isoformat(),
                "district": "",
                "subcounty": "",
                "parish": "",
                "nin": "",
                "learner_id": "",
                "is_active": "on",
            },
            campus=self.campus,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)

    def test_duplicate_active_teacher_staff_id_is_rejected_case_insensitively(self):
        TeacherProfile.objects.create(
            campus=self.campus,
            staff_id="STAFF-01",
            first_name="Existing",
            last_name="Teacher",
            is_active=True,
        )
        form = TeacherProfileForm(
            data={
                "campus": self.campus.pk,
                "staff_id": "staff-01",
                "first_name": "New",
                "last_name": "Teacher",
                "phone": "",
                "email": "",
                "is_active": "on",
            },
            campus_queryset=Campus.objects.filter(pk=self.campus.pk),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("staff_id", form.errors)
