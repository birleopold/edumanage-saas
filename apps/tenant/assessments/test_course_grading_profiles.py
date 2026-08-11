from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    Course,
    CourseOffering,
    GradeRange,
    GradingScale,
)

from .grading_forms import GradingProfileForm
from .grading_services import resolve_grading_profile
from .models import GradingProfile


class CourseSpecificGradingProfileTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(name="2042")
        self.term = AcademicTerm.objects.create(year=self.year, name="Term 1", order=1)
        self.math = Course.objects.create(name="Mathematics", code="MATH-2042")
        self.english = Course.objects.create(name="English", code="ENG-2042")

        self.general_scale = GradingScale.objects.create(name="General Scale 2042", is_default=True)
        GradeRange.objects.create(
            scale=self.general_scale,
            grade="P",
            min_score=50,
            max_score=100,
            remark="Pass",
            order=1,
        )
        GradeRange.objects.create(
            scale=self.general_scale,
            grade="F",
            min_score=0,
            max_score=49.99,
            remark="Below pass mark",
            order=2,
        )

        self.math_scale = GradingScale.objects.create(name="Mathematics Scale 2042")
        GradeRange.objects.create(
            scale=self.math_scale,
            grade="M",
            min_score=60,
            max_score=100,
            remark="Mathematics standard met",
            order=1,
        )
        GradeRange.objects.create(
            scale=self.math_scale,
            grade="N",
            min_score=0,
            max_score=59.99,
            remark="Mathematics standard not yet met",
            order=2,
        )

        self.math_offering = CourseOffering.objects.create(course=self.math, term=self.term)
        self.english_offering = CourseOffering.objects.create(course=self.english, term=self.term)

        self.general_profile = GradingProfile.objects.create(
            code="GENERAL-2042",
            name="General grading rule",
            grading_scale=self.general_scale,
            priority=10,
            is_default=True,
        )
        self.math_profile = GradingProfile.objects.create(
            code="MATH-2042",
            name="Mathematics grading rule",
            grading_scale=self.math_scale,
            course=self.math,
            priority=10,
        )

    def test_same_priority_course_rule_beats_general_rule_for_that_course(self):
        resolved = resolve_grading_profile(self.math_offering)

        self.assertEqual(resolved.pk, self.math_profile.pk)
        self.assertEqual(resolved.grading_scale_id, self.math_scale.pk)

    def test_course_rule_does_not_leak_to_another_subject(self):
        resolved = resolve_grading_profile(self.english_offering)

        self.assertEqual(resolved.pk, self.general_profile.pk)
        self.assertNotEqual(resolved.pk, self.math_profile.pk)

    def test_different_courses_can_have_same_priority_and_broader_scope(self):
        english_profile = GradingProfile(
            code="ENG-2042",
            name="English grading rule",
            grading_scale=self.general_scale,
            course=self.english,
            priority=10,
        )

        english_profile.full_clean()
        english_profile.save()

        self.assertEqual(resolve_grading_profile(self.english_offering).pk, english_profile.pk)

    def test_duplicate_course_scope_at_same_priority_is_rejected(self):
        duplicate = GradingProfile(
            code="MATH-DUPLICATE-2042",
            name="Duplicate Mathematics rule",
            grading_scale=self.math_scale,
            course=self.math,
            priority=10,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_scope_label_and_form_make_subject_override_visible(self):
        self.assertIn("Mathematics", self.math_profile.scope_label)
        self.assertIn("course", GradingProfileForm().fields)
        self.assertIn("subject/course", GradingProfileForm().fields["course"].help_text.lower())
