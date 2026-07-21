import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def normalize_clearance_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")


class ClearancePolicy(models.Model):
    ONLINE_EXAM = "ONLINE_EXAM"
    ASSESSMENT_RESULTS = "ASSESSMENT_RESULTS"
    ASSESSMENT_REPORT = "ASSESSMENT_REPORT"
    EXAM_RESULTS = "EXAM_RESULTS"
    EXAM_REPORT = "EXAM_REPORT"

    ACCESS_TYPE_CHOICES = (
        (ONLINE_EXAM, "Online examination access"),
        (ASSESSMENT_RESULTS, "Assessment results"),
        (ASSESSMENT_REPORT, "Assessment report card"),
        (EXAM_RESULTS, "Examination results"),
        (EXAM_REPORT, "Examination report card"),
    )

    ADVISORY = "ADVISORY"
    BLOCK = "BLOCK"
    ENFORCEMENT_CHOICES = (
        (ADVISORY, "Advisory warning only"),
        (BLOCK, "Block access when not cleared"),
    )

    FULL_PAYMENT = "FULL_PAYMENT"
    MINIMUM_PERCENTAGE = "MIN_PERCENT"
    MAXIMUM_BALANCE = "MAX_BALANCE"
    RULE_CHOICES = (
        (FULL_PAYMENT, "Require full payment"),
        (MINIMUM_PERCENTAGE, "Require minimum paid percentage"),
        (MAXIMUM_BALANCE, "Allow up to a maximum outstanding balance"),
    )

    CURRENT_TERM = "CURRENT_TERM"
    ALL_OPEN = "ALL_OPEN"
    BASIS_CHOICES = (
        (CURRENT_TERM, "Matching/current academic term invoices"),
        (ALL_OPEN, "All active invoices"),
    )

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    access_type = models.CharField(max_length=32, choices=ACCESS_TYPE_CHOICES)

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_policies",
    )
    stage = models.ForeignKey(
        "education_frameworks.EducationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_policies",
    )
    level = models.ForeignKey(
        "academics.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_policies",
    )
    program = models.ForeignKey(
        "academics.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_policies",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_policies",
    )

    calculation_basis = models.CharField(max_length=20, choices=BASIS_CHOICES, default=CURRENT_TERM)
    rule_type = models.CharField(max_length=20, choices=RULE_CHOICES, default=FULL_PAYMENT)
    minimum_paid_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    maximum_outstanding_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    allow_when_no_invoice = models.BooleanField(
        default=True,
        help_text="Keep access available when no invoice exists in the selected calculation basis.",
    )
    enforcement_mode = models.CharField(max_length=16, choices=ENFORCEMENT_CHOICES, default=ADVISORY)
    user_message = models.CharField(
        max_length=255,
        blank=True,
        help_text="Message shown when the learner does not meet this policy.",
    )
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "name")
        indexes = [
            models.Index(fields=["access_type", "is_active", "priority"]),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.code = normalize_clearance_code(self.code)
        errors = {}
        if not self.code:
            errors["code"] = "Enter a policy code."
        if self.rule_type == self.MINIMUM_PERCENTAGE:
            if not Decimal("0") <= self.minimum_paid_percentage <= Decimal("100"):
                errors["minimum_paid_percentage"] = "Percentage must be between 0 and 100."
        if self.rule_type == self.MAXIMUM_BALANCE and self.maximum_outstanding_balance < 0:
            errors["maximum_outstanding_balance"] = "Maximum balance cannot be negative."
        if self.calculation_basis == self.CURRENT_TERM and not self.academic_term_id:
            # A runtime target term may still be supplied; this remains valid as a current-term default.
            pass
        if self.is_active:
            duplicate = type(self).objects.filter(
                access_type=self.access_type,
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
                errors["__all__"] = "Another active policy has the same access type, scope and priority."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_clearance_code(self.code)
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


class ClearanceOverride(models.Model):
    ALL = "ALL"
    ACCESS_TYPE_CHOICES = ((ALL, "All clearance-controlled access"),) + ClearancePolicy.ACCESS_TYPE_CHOICES

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="clearance_overrides",
    )
    policy = models.ForeignKey(
        ClearancePolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overrides",
    )
    access_type = models.CharField(max_length=32, choices=ACCESS_TYPE_CHOICES, default=ALL)
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_overrides",
    )
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    reason = models.TextField()
    reference = models.CharField(max_length=96, blank=True)
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_overrides_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "is_active", "valid_from", "valid_until"])]

    def __str__(self) -> str:
        return f"{self.student} — {self.get_access_type_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.valid_until and self.valid_until < self.valid_from:
            errors["valid_until"] = "The end date cannot be before the start date."
        if self.policy_id and self.access_type not in (self.ALL, self.policy.access_type):
            errors["access_type"] = "The override access type must match the selected policy or apply to all access."
        if self.policy_id and self.academic_term_id and self.policy.academic_term_id:
            if self.academic_term_id != self.policy.academic_term_id:
                errors["academic_term"] = "The override term must match the selected policy term."
        if errors:
            raise ValidationError(errors)

    def is_valid_on(self, value=None) -> bool:
        day = value or timezone.localdate()
        return bool(
            self.is_active
            and self.valid_from <= day
            and (self.valid_until is None or self.valid_until >= day)
        )


class ClearanceDecisionLog(models.Model):
    ALLOWED = "ALLOWED"
    ADVISED = "ADVISED"
    BLOCKED = "BLOCKED"
    OVERRIDDEN = "OVERRIDDEN"
    DECISION_CHOICES = (
        (ALLOWED, "Allowed"),
        (ADVISED, "Allowed with advisory"),
        (BLOCKED, "Blocked"),
        (OVERRIDDEN, "Allowed by override"),
    )

    PORTAL = "PORTAL"
    ADMIN = "ADMIN"
    COMMAND = "COMMAND"
    SOURCE_CHOICES = ((PORTAL, "Portal"), (ADMIN, "Administrator check"), (COMMAND, "Command audit"))

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="clearance_decision_logs",
    )
    policy = models.ForeignKey(
        ClearancePolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decision_logs",
    )
    override = models.ForeignKey(
        ClearanceOverride,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decision_logs",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_decision_logs",
    )
    access_type = models.CharField(max_length=32, choices=ClearancePolicy.ACCESS_TYPE_CHOICES)
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=PORTAL)
    invoiced_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    outstanding_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    paid_percentage = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0"))
    reason = models.CharField(max_length=255, blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_decisions_checked",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "access_type", "created_at"])]

    def __str__(self) -> str:
        return f"{self.student} — {self.access_type} — {self.decision}"
