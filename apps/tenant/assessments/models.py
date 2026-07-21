import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def normalize_assessment_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")


class AssessmentType(models.Model):
    CONTINUOUS = "CONTINUOUS"
    EXAMINATION = "EXAMINATION"
    COURSEWORK = "COURSEWORK"
    PROJECT = "PROJECT"
    PRACTICAL = "PRACTICAL"
    COMPETENCY = "COMPETENCY"
    ORAL = "ORAL"
    OTHER = "OTHER"

    KIND_CHOICES = (
        (CONTINUOUS, "Continuous Assessment"),
        (EXAMINATION, "Examination"),
        (COURSEWORK, "Coursework"),
        (PROJECT, "Project"),
        (PRACTICAL, "Practical"),
        (COMPETENCY, "Competency Activity"),
        (ORAL, "Oral or Presentation"),
        (OTHER, "Other"),
    )

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=96)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default=CONTINUOUS)
    description = models.TextField(blank=True)
    local_aliases = models.JSONField(default=dict, blank=True)
    default_max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    default_weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind", "name")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.code = normalize_assessment_code(self.code)
        if self.default_max_score is not None and self.default_max_score <= 0:
            raise ValidationError({"default_max_score": "Default maximum score must be greater than zero."})
        if self.default_weight is not None and self.default_weight < 0:
            raise ValidationError({"default_weight": "Default weight cannot be negative."})

    def save(self, *args, **kwargs):
        self.code = normalize_assessment_code(self.code)
        super().save(*args, **kwargs)

    def display_name(self, country_code: str = "") -> str:
        aliases = dict(self.local_aliases or {})
        return str(aliases.get((country_code or "").upper()) or self.name)


class AssessmentWeightingScheme(models.Model):
    IGNORE_MISSING = "IGNORE"
    ZERO_MISSING = "ZERO"
    REQUIRE_COMPLETE = "INCOMPLETE"

    MISSING_SCORE_POLICY_CHOICES = (
        (IGNORE_MISSING, "Ignore missing assessments and normalize completed work"),
        (ZERO_MISSING, "Treat missing required assessments as zero"),
        (REQUIRE_COMPLETE, "Mark result incomplete until required assessments are entered"),
    )

    code = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_weighting_schemes",
    )
    stage = models.ForeignKey(
        "education_frameworks.EducationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_weighting_schemes",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_weighting_schemes",
    )
    program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_weighting_schemes",
    )
    total_weight = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    missing_score_policy = models.CharField(
        max_length=16,
        choices=MISSING_SCORE_POLICY_CHOICES,
        default=REQUIRE_COMPLETE,
    )
    normalize_to_total = models.BooleanField(
        default=True,
        help_text="Normalize completed component weights to a percentage when the policy permits it.",
    )
    priority = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "-is_default", "name")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.code = normalize_assessment_code(self.code)
        errors = {}
        if self.total_weight is not None and self.total_weight <= 0:
            errors["total_weight"] = "Total weight must be greater than zero."
        if self.is_active:
            duplicate = type(self).objects.filter(
                campus_id=self.campus_id,
                stage_id=self.stage_id,
                academic_term_id=self.academic_term_id,
                program_id=self.program_id,
                priority=self.priority,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["__all__"] = "Another active scheme has the same scope and priority."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_assessment_code(self.code)
        super().save(*args, **kwargs)

    @property
    def scope_label(self) -> str:
        parts = []
        if self.campus_id:
            parts.append(str(self.campus))
        if self.stage_id:
            parts.append(str(self.stage))
        if self.academic_term_id:
            parts.append(str(self.academic_term))
        if self.program_id:
            parts.append(str(self.program))
        return " · ".join(parts) if parts else "Institution default"


class AssessmentWeightingComponent(models.Model):
    AVERAGE = "AVERAGE"
    BEST = "BEST"
    LATEST = "LATEST"

    AGGREGATION_CHOICES = (
        (AVERAGE, "Average completed assessments"),
        (BEST, "Best completed assessment"),
        (LATEST, "Latest completed assessment"),
    )

    scheme = models.ForeignKey(
        AssessmentWeightingScheme,
        on_delete=models.CASCADE,
        related_name="components",
    )
    assessment_type = models.ForeignKey(
        AssessmentType,
        on_delete=models.PROTECT,
        related_name="weighting_components",
    )
    weight = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    aggregation_method = models.CharField(
        max_length=16,
        choices=AGGREGATION_CHOICES,
        default=AVERAGE,
    )
    minimum_occurrences = models.PositiveSmallIntegerField(default=1)
    maximum_occurrences = models.PositiveSmallIntegerField(null=True, blank=True)
    drop_lowest_count = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=1)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheme", "order", "assessment_type__name")
        constraints = [
            models.UniqueConstraint(
                fields=("scheme", "assessment_type"),
                name="uniq_scheme_assessment_type",
            )
        ]

    def __str__(self) -> str:
        return f"{self.scheme}: {self.assessment_type} ({self.weight})"

    def clean(self):
        super().clean()
        errors = {}
        if self.weight is not None and self.weight <= 0:
            errors["weight"] = "Component weight must be greater than zero."
        if self.minimum_occurrences < 1:
            errors["minimum_occurrences"] = "Minimum occurrences must be at least one."
        if self.maximum_occurrences is not None and self.maximum_occurrences < self.minimum_occurrences:
            errors["maximum_occurrences"] = "Maximum occurrences cannot be below the minimum occurrences."
        limit = self.maximum_occurrences or self.minimum_occurrences
        if self.drop_lowest_count >= limit:
            errors["drop_lowest_count"] = "At least one assessment must remain after dropping low scores."
        if self.assessment_type_id and not self.assessment_type.is_active:
            errors["assessment_type"] = "Choose an active assessment type."
        if self.scheme_id and not self.scheme.is_active and self.is_active:
            errors["scheme"] = "An active component cannot belong to an inactive scheme."
        if errors:
            raise ValidationError(errors)


class GradingProfile(models.Model):
    MEAN = "MEAN"
    CREDIT_WEIGHTED = "CREDIT_WEIGHTED"

    OVERALL_AGGREGATION_CHOICES = (
        (MEAN, "Mean of completed course results"),
        (CREDIT_WEIGHTED, "Credit-weighted mean"),
    )

    EXCLUDE_INCOMPLETE = "EXCLUDE"
    ZERO_INCOMPLETE = "ZERO"
    REQUIRE_COMPLETE = "INCOMPLETE"

    INCOMPLETE_RESULT_POLICY_CHOICES = (
        (EXCLUDE_INCOMPLETE, "Exclude incomplete courses from the overall result"),
        (ZERO_INCOMPLETE, "Treat incomplete courses as zero"),
        (REQUIRE_COMPLETE, "Keep the report incomplete until every course is complete"),
    )

    code = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    grading_scale = models.ForeignKey(
        "academics.GradingScale",
        on_delete=models.PROTECT,
        related_name="grading_profiles",
    )
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grading_profiles",
    )
    stage = models.ForeignKey(
        "education_frameworks.EducationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grading_profiles",
    )
    level = models.ForeignKey(
        "academics.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grading_profiles",
    )
    program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grading_profiles",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grading_profiles",
    )
    overall_aggregation = models.CharField(
        max_length=24,
        choices=OVERALL_AGGREGATION_CHOICES,
        default=MEAN,
    )
    incomplete_result_policy = models.CharField(
        max_length=16,
        choices=INCOMPLETE_RESULT_POLICY_CHOICES,
        default=EXCLUDE_INCOMPLETE,
    )
    pass_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    promotion_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    minimum_passed_courses = models.PositiveSmallIntegerField(null=True, blank=True)
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        validators=[MaxValueValidator(4)],
    )
    priority = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "-is_default", "name")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.code = normalize_assessment_code(self.code)
        errors = {}
        if self.grading_scale_id and not self.grading_scale.is_active:
            errors["grading_scale"] = "Choose an active grading scale."
        if self.pass_percentage is not None and not Decimal("0") <= self.pass_percentage <= Decimal("100"):
            errors["pass_percentage"] = "Pass percentage must be between 0 and 100."
        if (
            self.promotion_percentage is not None
            and not Decimal("0") <= self.promotion_percentage <= Decimal("100")
        ):
            errors["promotion_percentage"] = "Promotion percentage must be between 0 and 100."
        if self.is_active:
            duplicate = type(self).objects.filter(
                campus_id=self.campus_id,
                stage_id=self.stage_id,
                level_id=self.level_id,
                program_id=self.program_id,
                academic_term_id=self.academic_term_id,
                priority=self.priority,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["__all__"] = "Another active grading profile has the same scope and priority."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_assessment_code(self.code)
        super().save(*args, **kwargs)

    @property
    def scope_label(self) -> str:
        parts = []
        if self.campus_id:
            parts.append(str(self.campus))
        if self.stage_id:
            parts.append(str(self.stage))
        if self.level_id:
            parts.append(str(self.level))
        if self.program_id:
            parts.append(str(self.program))
        if self.academic_term_id:
            parts.append(str(self.academic_term))
        return " · ".join(parts) if parts else "Institution default"


class ReportRule(models.Model):
    grading_profile = models.OneToOneField(
        GradingProfile,
        on_delete=models.CASCADE,
        related_name="report_rule",
    )
    report_title = models.CharField(max_length=128, blank=True)
    result_label = models.CharField(max_length=48, default="Result")
    promotion_label = models.CharField(max_length=48, default="Progression")
    show_percentage = models.BooleanField(default=True)
    show_grade = models.BooleanField(default=True)
    show_remark = models.BooleanField(default=True)
    show_published_scores = models.BooleanField(default=True)
    show_assessment_details = models.BooleanField(default=True)
    show_component_breakdown = models.BooleanField(default=True)
    show_promotion_status = models.BooleanField(default=False)
    show_teacher_comments = models.BooleanField(default=True)
    show_head_comments = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Report rules — {self.grading_profile}"


class Assessment(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    assessment_type = models.ForeignKey(
        AssessmentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
    )
    weighting_component = models.ForeignKey(
        AssessmentWeightingComponent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
    )
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("offering", "name")

    def __str__(self) -> str:
        return f"{self.offering} - {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.max_score is not None and self.max_score <= 0:
            errors["max_score"] = "Maximum score must be greater than zero."
        if self.weight is not None and self.weight < 0:
            errors["weight"] = "Weight cannot be negative."
        if self.assessment_type_id and not self.assessment_type.is_active:
            errors["assessment_type"] = "Choose an active assessment type."
        if self.weighting_component_id:
            component_type_id = self.weighting_component.assessment_type_id
            if self.assessment_type_id and self.assessment_type_id != component_type_id:
                errors["weighting_component"] = "The weighting component must use the selected assessment type."
            if not self.weighting_component.is_active or not self.weighting_component.scheme.is_active:
                errors["weighting_component"] = "Choose a component from an active weighting scheme."
        if errors:
            raise ValidationError(errors)


class AssessmentScore(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="scores")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    report_comment = models.TextField(blank=True)
    report_comment_ai_assisted = models.BooleanField(default=False)
    graded_by = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")
        unique_together = ("assessment", "student")

    def __str__(self) -> str:
        return f"{self.student} -> {self.assessment}"
