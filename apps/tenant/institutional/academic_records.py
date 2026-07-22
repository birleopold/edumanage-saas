from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class AcademicAttemptPolicy(models.Model):
    LATEST = "LATEST"
    BEST = "BEST"
    ORIGINAL = "ORIGINAL"
    REPLACEMENT_CHOICES = (
        (LATEST, "Latest completed attempt replaces earlier attempts"),
        (BEST, "Best completed attempt counts toward GPA"),
        (ORIGINAL, "Original attempt remains in GPA unless manually excluded"),
    )

    name = models.CharField(max_length=160)
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="academic_attempt_policies",
    )
    program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="academic_attempt_policies",
    )
    level = models.ForeignKey(
        "academics.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="academic_attempt_policies",
    )
    replacement_mode = models.CharField(
        max_length=16,
        choices=REPLACEMENT_CHOICES,
        default=LATEST,
    )
    maximum_attempts = models.PositiveSmallIntegerField(default=3)
    supplementary_max_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    pass_grade_point = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    probation_cgpa = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    dismissal_cgpa = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    priority = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "-is_default", "name")

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        if self.maximum_attempts < 1:
            errors["maximum_attempts"] = "Maximum attempts must be at least one."
        if (
            self.supplementary_max_percentage is not None
            and not Decimal("0") <= self.supplementary_max_percentage <= Decimal("100")
        ):
            errors["supplementary_max_percentage"] = (
                "Supplementary maximum percentage must be between 0 and 100."
            )
        if (
            self.dismissal_cgpa is not None
            and self.dismissal_cgpa > self.probation_cgpa
        ):
            errors["dismissal_cgpa"] = (
                "Dismissal CGPA cannot be above the probation threshold."
            )
        if self.is_active:
            duplicate = type(self).objects.filter(
                campus_id=self.campus_id,
                program_id=self.program_id,
                level_id=self.level_id,
                priority=self.priority,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["__all__"] = (
                    "Another active attempt policy has the same scope and priority."
                )
        if errors:
            raise ValidationError(errors)


class SemesterRegistration(models.Model):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = (
        (REGISTERED, "Registered"),
        (ACTIVE, "Active"),
        (COMPLETED, "Completed"),
        (WITHDRAWN, "Withdrawn"),
        (CANCELLED, "Cancelled"),
    )

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="semester_registrations",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.PROTECT,
        related_name="semester_registrations",
    )
    program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semester_registrations",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=REGISTERED,
    )
    registration_reference = models.CharField(max_length=96, blank=True)
    registered_on = models.DateField(default=timezone.localdate)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semester_registrations_recorded",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semester_registrations_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "-academic_term__year__name",
            "-academic_term__order",
            "student__last_name",
        )
        constraints = [
            models.UniqueConstraint(
                fields=("student", "academic_term"),
                name="uniq_student_semester_registration",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.academic_term}"

    def clean(self):
        super().clean()
        errors = {}
        class_group = getattr(getattr(self.student, "stream", None), "class_group", None)
        learner_program_id = getattr(class_group, "program_id", None)
        if self.program_id and learner_program_id and self.program_id != learner_program_id:
            errors["program"] = "The programme does not match the learner's current placement."
        if self.status == self.COMPLETED and self.attempts.exclude(
            status=CourseAttempt.COMPLETED
        ).exists():
            errors["status"] = (
                "Complete or withdraw every course attempt before completing the semester registration."
            )
        if errors:
            raise ValidationError(errors)


class CourseAttempt(models.Model):
    ORDINARY = "ORDINARY"
    RETAKE = "RETAKE"
    SUPPLEMENTARY = "SUPPLEMENTARY"
    REPEAT = "REPEAT"
    ATTEMPT_TYPE_CHOICES = (
        (ORDINARY, "Ordinary attempt"),
        (RETAKE, "Retake"),
        (SUPPLEMENTARY, "Supplementary examination"),
        (REPEAT, "Repeated course"),
    )

    REGISTERED = "REGISTERED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"
    DEFERRED = "DEFERRED"
    STATUS_CHOICES = (
        (REGISTERED, "Registered"),
        (IN_PROGRESS, "In progress"),
        (COMPLETED, "Completed"),
        (WITHDRAWN, "Withdrawn"),
        (DEFERRED, "Deferred"),
    )

    registration = models.ForeignKey(
        SemesterRegistration,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.PROTECT,
        related_name="academic_attempts",
    )
    offering = models.ForeignKey(
        "academics.CourseOffering",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="academic_attempts",
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    attempt_type = models.CharField(
        max_length=20,
        choices=ATTEMPT_TYPE_CHOICES,
        default=ORDINARY,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=REGISTERED,
    )
    score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    grade = models.CharField(max_length=16, blank=True)
    grade_point = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    credits = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    counts_toward_gpa = models.BooleanField(default=True)
    replaced_attempt = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_attempts",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="course_attempts_registered",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="course_attempts_approved",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "registration__academic_term__year__name",
            "registration__academic_term__order",
            "course__name",
            "attempt_number",
        )
        constraints = [
            models.UniqueConstraint(
                fields=("registration", "course", "attempt_number"),
                name="uniq_semester_course_attempt_number",
            )
        ]
        indexes = [
            models.Index(fields=("course", "attempt_type", "status")),
        ]

    def __str__(self):
        return (
            f"{self.registration.student} — {self.course} "
            f"attempt {self.attempt_number}"
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.offering_id:
            if self.offering.course_id != self.course_id:
                errors["offering"] = "The offering must use the selected course."
            if self.offering.term_id != self.registration.academic_term_id:
                errors["offering"] = (
                    "The offering must belong to the registration academic term."
                )
        policy = resolve_attempt_policy_for_registration(self.registration)
        if policy and self.attempt_number > policy.maximum_attempts:
            errors["attempt_number"] = (
                "The maximum attempts configured for this programme have been exceeded."
            )
        if self.attempt_number == 1 and self.attempt_type != self.ORDINARY:
            errors["attempt_type"] = "The first attempt must be an ordinary attempt."
        if self.attempt_number > 1 and self.attempt_type == self.ORDINARY:
            errors["attempt_type"] = (
                "Later attempts must be retakes, supplementary examinations, or repeats."
            )
        if self.replaced_attempt_id:
            if self.replaced_attempt.registration.student_id != self.registration.student_id:
                errors["replaced_attempt"] = (
                    "The replaced attempt must belong to the same learner."
                )
            if self.replaced_attempt.course_id != self.course_id:
                errors["replaced_attempt"] = (
                    "The replaced attempt must use the same course."
                )
            if self.replaced_attempt.attempt_number >= self.attempt_number:
                errors["replaced_attempt"] = (
                    "A replacement must point to an earlier attempt."
                )
        if self.status == self.COMPLETED:
            if self.grade_point is None:
                errors["grade_point"] = (
                    "Record a grade point before completing an attempt."
                )
            if self.completed_at is None:
                errors["completed_at"] = (
                    "Record the completion time before completing an attempt."
                )
        if (
            policy
            and self.attempt_type == self.SUPPLEMENTARY
            and policy.supplementary_max_percentage is not None
            and self.percentage is not None
            and self.percentage > policy.supplementary_max_percentage
        ):
            errors["percentage"] = (
                "The supplementary result exceeds the configured maximum percentage."
            )
        if errors:
            raise ValidationError(errors)


class AcademicStanding(models.Model):
    GOOD = "GOOD"
    WARNING = "WARNING"
    PROBATION = "PROBATION"
    DISMISSED = "DISMISSED"
    COMPLETED = "COMPLETED"
    STANDING_CHOICES = (
        (GOOD, "Good standing"),
        (WARNING, "Academic warning"),
        (PROBATION, "Academic probation"),
        (DISMISSED, "Dismissed"),
        (COMPLETED, "Programme completed"),
    )

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="academic_standings",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.PROTECT,
        related_name="academic_standings",
    )
    semester_gpa = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    cumulative_gpa = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    attempted_credits = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    earned_credits = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    standing = models.CharField(
        max_length=16,
        choices=STANDING_CHOICES,
        default=GOOD,
    )
    progression_decision = models.CharField(max_length=96, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(default=timezone.now)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="academic_standings_calculated",
    )

    class Meta:
        ordering = (
            "-academic_term__year__name",
            "-academic_term__order",
        )
        constraints = [
            models.UniqueConstraint(
                fields=("student", "academic_term"),
                name="uniq_student_term_academic_standing",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.academic_term} — {self.get_standing_display()}"


def resolve_attempt_policy_for_registration(registration):
    class_group = getattr(
        getattr(registration.student, "stream", None),
        "class_group",
        None,
    )
    level_id = getattr(class_group, "level_id", None)
    program_id = registration.program_id or getattr(class_group, "program_id", None)
    campus_id = registration.student.campus_id
    candidates = list(
        AcademicAttemptPolicy.objects.filter(is_active=True)
        .filter(
            models.Q(campus__isnull=True) | models.Q(campus_id=campus_id),
            models.Q(program__isnull=True) | models.Q(program_id=program_id),
            models.Q(level__isnull=True) | models.Q(level_id=level_id),
        )
        .order_by("-priority", "-is_default", "-pk")
    )
    candidates.sort(
        key=lambda policy: (
            policy.priority,
            bool(policy.campus_id),
            bool(policy.program_id),
            bool(policy.level_id),
            policy.is_default,
            policy.pk,
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None
