from django.core.exceptions import ValidationError
from django.db import models


class EducationStage(models.Model):
    ECD = "ECD"
    PRIMARY = "PRIMARY"
    LOWER_SECONDARY = "LOWER_SECONDARY"
    UPPER_SECONDARY = "UPPER_SECONDARY"
    TERTIARY = "TERTIARY"
    UNIVERSITY = "UNIVERSITY"
    OTHER = "OTHER"

    PERIOD_TERM = "TERM"
    PERIOD_SEMESTER = "SEMESTER"
    PERIOD_YEAR = "YEAR"
    PERIOD_CUSTOM = "CUSTOM"

    PERIOD_TYPE_CHOICES = (
        (PERIOD_TERM, "Term"),
        (PERIOD_SEMESTER, "Semester"),
        (PERIOD_YEAR, "Academic Year"),
        (PERIOD_CUSTOM, "Custom Period"),
    )

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=96)
    local_name = models.CharField(max_length=96, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=1)
    default_period_type = models.CharField(
        max_length=16,
        choices=PERIOD_TYPE_CHOICES,
        default=PERIOD_TERM,
    )
    settings = models.JSONField(default=dict, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.local_name or self.name


class AcademicFramework(models.Model):
    code = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=160)
    country_code = models.CharField(max_length=2, blank=True)
    description = models.TextField(blank=True)
    default_terminology = models.JSONField(default=dict, blank=True)
    default_settings = models.JSONField(default=dict, blank=True)
    is_system_template = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("country_code", "name")

    def __str__(self) -> str:
        return self.name


class FrameworkStage(models.Model):
    framework = models.ForeignKey(
        AcademicFramework,
        on_delete=models.CASCADE,
        related_name="stage_settings",
    )
    stage = models.ForeignKey(
        EducationStage,
        on_delete=models.CASCADE,
        related_name="framework_settings",
    )
    local_name = models.CharField(max_length=96, blank=True)
    class_label = models.CharField(max_length=48, default="Class")
    subject_label = models.CharField(max_length=48, default="Subject")
    period_label = models.CharField(max_length=48, default="Term")
    report_label = models.CharField(max_length=48, default="Report Card")
    candidate_class = models.BooleanField(default=False)
    terminology = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("framework", "stage__order")
        constraints = [
            models.UniqueConstraint(
                fields=["framework", "stage"],
                name="uniq_framework_stage",
            )
        ]

    def __str__(self) -> str:
        return f"{self.framework} — {self.local_name or self.stage.name}"


class InstitutionEducationProfile(models.Model):
    ECD = "ECD"
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    TERTIARY = "TERTIARY"
    UNIVERSITY = "UNIVERSITY"
    MIXED = "MIXED"
    OTHER = "OTHER"

    INSTITUTION_TYPE_CHOICES = (
        (ECD, "Early Childhood Centre"),
        (PRIMARY, "Primary School"),
        (SECONDARY, "Secondary School"),
        (TERTIARY, "Tertiary or Vocational Institution"),
        (UNIVERSITY, "University"),
        (MIXED, "Mixed Institution"),
        (OTHER, "Other Institution"),
    )

    organization = models.OneToOneField(
        "orgsettings.OrganizationProfile",
        on_delete=models.CASCADE,
        related_name="education_profile",
    )
    institution_type = models.CharField(
        max_length=24,
        choices=INSTITUTION_TYPE_CHOICES,
        default=MIXED,
    )
    country_code = models.CharField(max_length=2, default="UG")
    locale = models.CharField(max_length=16, default="en-UG")
    primary_framework = models.ForeignKey(
        AcademicFramework,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institution_profiles",
    )
    terminology = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    use_local_terminology = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("organization__name",)

    def __str__(self) -> str:
        return f"{self.organization} education profile"


class CampusEducationStage(models.Model):
    profile = models.ForeignKey(
        InstitutionEducationProfile,
        on_delete=models.CASCADE,
        related_name="campus_stages",
    )
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.CASCADE,
        related_name="education_stages",
    )
    stage = models.ForeignKey(
        EducationStage,
        on_delete=models.PROTECT,
        related_name="campus_configurations",
    )
    framework_stage = models.ForeignKey(
        FrameworkStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campus_configurations",
    )
    local_name = models.CharField(max_length=96, blank=True)
    academic_period_type = models.CharField(
        max_length=16,
        choices=EducationStage.PERIOD_TYPE_CHOICES,
        default=EducationStage.PERIOD_TERM,
    )
    grading_scale_id = models.PositiveBigIntegerField(null=True, blank=True)
    grading_scale_name = models.CharField(max_length=128, blank=True)
    report_layout_key = models.CharField(max_length=64, blank=True)
    terminology = models.JSONField(default=dict, blank=True)
    candidate_settings = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("campus__name", "stage__order")
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "stage"],
                name="uniq_campus_education_stage",
            )
        ]

    def clean(self):
        super().clean()
        if self.profile_id and self.campus_id:
            if self.profile.organization_id != self.campus.organization_id:
                raise ValidationError(
                    {"campus": "Campus must belong to the profile's organization."}
                )
        if self.framework_stage_id and self.profile.primary_framework_id:
            if self.framework_stage.framework_id != self.profile.primary_framework_id:
                raise ValidationError(
                    {"framework_stage": "Framework stage must belong to the profile's primary framework."}
                )
        if self.framework_stage_id and self.framework_stage.stage_id != self.stage_id:
            raise ValidationError(
                {"framework_stage": "Framework stage must match the selected education stage."}
            )

    def __str__(self) -> str:
        return f"{self.campus} — {self.local_name or self.stage.name}"


class LevelStageMapping(models.Model):
    """Compatibility link to existing academics.Level records without altering them."""

    profile = models.ForeignKey(
        InstitutionEducationProfile,
        on_delete=models.CASCADE,
        related_name="level_mappings",
    )
    stage = models.ForeignKey(
        EducationStage,
        on_delete=models.PROTECT,
        related_name="legacy_level_mappings",
    )
    legacy_level_id = models.PositiveBigIntegerField()
    legacy_level_name = models.CharField(max_length=128)
    local_name = models.CharField(max_length=128, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("legacy_level_name",)
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "legacy_level_id"],
                name="uniq_profile_legacy_level",
            )
        ]

    def __str__(self) -> str:
        return f"{self.legacy_level_name} → {self.stage.code}"
