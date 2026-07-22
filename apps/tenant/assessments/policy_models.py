from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class AssessmentPolicy(models.Model):
    NUMERIC = "NUMERIC"
    COMPETENCY = "COMPETENCY"
    MIXED = "MIXED"
    GRADING_MODE_CHOICES = (
        (NUMERIC, "Numeric marks and grades"),
        (COMPETENCY, "Competency or developmental assessment"),
        (MIXED, "Mixed numeric and competency assessment"),
    )

    MISSING = "MISSING"
    ZERO = "ZERO"
    EXCUSED = "EXCUSED"
    DEFERRED = "DEFERRED"
    MAKEUP_REQUIRED = "MAKEUP_REQUIRED"
    ABSENCE_POLICY_CHOICES = (
        (MISSING, "Leave the result missing"),
        (ZERO, "Treat an unexplained absence as zero"),
        (EXCUSED, "Exclude an excused absence"),
        (DEFERRED, "Defer the result until a later assessment"),
        (MAKEUP_REQUIRED, "Require a makeup assessment"),
    )

    assessment = models.OneToOneField(
        "assessments.Assessment",
        on_delete=models.CASCADE,
        related_name="policy",
    )
    grading_mode = models.CharField(
        max_length=16,
        choices=GRADING_MODE_CHOICES,
        default=NUMERIC,
    )
    absence_policy = models.CharField(
        max_length=24,
        choices=ABSENCE_POLICY_CHOICES,
        default=MISSING,
    )
    show_on_report = models.BooleanField(
        default=True,
        help_text="Include this assessment in report-card and transcript calculations when it is published.",
    )
    allow_makeup = models.BooleanField(default=False)
    responsible_teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_policies_responsible",
    )
    competency_framework_key = models.CharField(max_length=96, blank=True)
    makeup_for = models.ForeignKey(
        "assessments.Assessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="makeup_policy_records",
    )
    deferred_until = models.DateField(null=True, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("assessment__offering", "assessment__name")

    def __str__(self):
        return f"Policy — {self.assessment}"

    def clean(self):
        super().clean()
        errors = {}
        if self.responsible_teacher_id:
            offering = self.assessment.offering
            teacher_campus_id = self.responsible_teacher.campus_id
            offering_campus_id = offering.campus_id or getattr(
                offering.class_group,
                "campus_id",
                None,
            )
            if teacher_campus_id and offering_campus_id and teacher_campus_id != offering_campus_id:
                errors["responsible_teacher"] = (
                    "The responsible teacher belongs to another campus."
                )
        if self.makeup_for_id:
            if self.makeup_for_id == self.assessment_id:
                errors["makeup_for"] = "An assessment cannot be its own makeup assessment."
            elif self.makeup_for.offering_id != self.assessment.offering_id:
                errors["makeup_for"] = (
                    "The original and makeup assessments must use the same course offering."
                )
            else:
                original_policy = getattr(self.makeup_for, "policy", None)
                if original_policy and not original_policy.allow_makeup:
                    errors["makeup_for"] = (
                        "The original assessment does not permit a makeup assessment."
                    )
        if self.absence_policy in {self.DEFERRED, self.MAKEUP_REQUIRED} and not self.allow_makeup:
            errors["allow_makeup"] = (
                "Deferred or makeup-required absence policies must allow a makeup assessment."
            )
        if errors:
            raise ValidationError(errors)


class AssessmentScorePolicy(models.Model):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"
    DEFERRED = "DEFERRED"
    MAKEUP_PENDING = "MAKEUP_PENDING"
    STATUS_CHOICES = (
        (PRESENT, "Present"),
        (ABSENT, "Absent"),
        (EXCUSED, "Excused absence"),
        (DEFERRED, "Deferred"),
        (MAKEUP_PENDING, "Makeup assessment pending"),
    )

    ACHIEVED = "ACHIEVED"
    DEVELOPING = "DEVELOPING"
    NEEDS_SUPPORT = "NEEDS_SUPPORT"
    NOT_ASSESSED = "NOT_ASSESSED"
    COMPETENCY_CHOICES = (
        (ACHIEVED, "Achieved"),
        (DEVELOPING, "Developing"),
        (NEEDS_SUPPORT, "Needs support"),
        (NOT_ASSESSED, "Not assessed"),
    )

    score_record = models.OneToOneField(
        "assessments.AssessmentScore",
        on_delete=models.CASCADE,
        related_name="policy",
    )
    attendance_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PRESENT,
    )
    competency_rating = models.CharField(
        max_length=24,
        choices=COMPETENCY_CHOICES,
        default=NOT_ASSESSED,
    )
    competency_evidence = models.TextField(blank=True)
    deferred_until = models.DateField(null=True, blank=True)
    makeup_completed_by = models.ForeignKey(
        "assessments.AssessmentScore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_makeup_for",
    )
    settings = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "score_record__student__last_name",
            "score_record__student__first_name",
        )

    def __str__(self):
        return f"Result policy — {self.score_record}"

    @property
    def assessment_policy(self):
        return getattr(self.score_record.assessment, "policy", None)

    @property
    def effective_score(self):
        if self.attendance_status == self.PRESENT:
            return self.score_record.score
        policy = self.assessment_policy
        if (
            self.attendance_status == self.ABSENT
            and policy
            and policy.absence_policy == AssessmentPolicy.ZERO
        ):
            return Decimal("0")
        return None

    def clean(self):
        super().clean()
        errors = {}
        policy = self.assessment_policy
        if self.attendance_status != self.PRESENT and self.score_record.score is not None:
            zero_is_allowed = bool(
                self.attendance_status == self.ABSENT
                and policy
                and policy.absence_policy == AssessmentPolicy.ZERO
                and Decimal(self.score_record.score) == Decimal("0")
            )
            if not zero_is_allowed:
                errors["attendance_status"] = (
                    "Clear the numeric score when the learner was not present."
                )
        if self.attendance_status in {self.DEFERRED, self.MAKEUP_PENDING}:
            if policy and not policy.allow_makeup:
                errors["attendance_status"] = (
                    "This assessment does not permit deferred or makeup results."
                )
        if self.makeup_completed_by_id:
            replacement = self.makeup_completed_by
            if replacement.student_id != self.score_record.student_id:
                errors["makeup_completed_by"] = (
                    "The replacement score must belong to the same learner."
                )
            replacement_policy = getattr(replacement.assessment, "policy", None)
            if not replacement_policy or replacement_policy.makeup_for_id != self.score_record.assessment_id:
                errors["makeup_completed_by"] = (
                    "The replacement score must come from a configured makeup assessment."
                )
        if policy and policy.grading_mode == AssessmentPolicy.COMPETENCY:
            if self.attendance_status == self.PRESENT and self.competency_rating == self.NOT_ASSESSED:
                errors["competency_rating"] = (
                    "Record a competency rating for a present learner in competency mode."
                )
        if errors:
            raise ValidationError(errors)
