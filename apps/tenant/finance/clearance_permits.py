from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ClearancePermitSnapshot(models.Model):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (REVOKED, "Revoked"),
        (EXPIRED, "Expired"),
    )

    decision_log = models.OneToOneField(
        "finance.ClearanceDecisionLog",
        on_delete=models.PROTECT,
        related_name="permit_snapshot",
    )
    permit = models.OneToOneField(
        "institutional.VerifiablePermit",
        on_delete=models.PROTECT,
        related_name="clearance_snapshot",
    )
    policy_code = models.CharField(max_length=64, blank=True)
    access_type = models.CharField(max_length=32)
    decision = models.CharField(max_length=16)
    invoiced_amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2)
    outstanding_balance = models.DecimalField(max_digits=14, decimal_places=2)
    paid_percentage = models.DecimalField(max_digits=7, decimal_places=2)
    rule_snapshot = models.JSONField(default=dict)
    override_snapshot = models.JSONField(default=dict, blank=True)
    academic_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=ACTIVE,
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_permits_issued",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_permits_revoked",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-issued_at",)
        indexes = [
            models.Index(fields=("access_type", "status", "valid_until")),
        ]

    def __str__(self):
        return f"{self.permit.reference} — {self.access_type}"

    @property
    def is_valid(self):
        now = timezone.now()
        return bool(
            self.status == self.ACTIVE
            and self.valid_from <= now <= self.valid_until
            and self.permit.is_valid
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.valid_until <= self.valid_from:
            errors["valid_until"] = "Permit expiry must be after its start time."
        if self.decision_log_id:
            log = self.decision_log
            if log.decision not in {log.ALLOWED, log.OVERRIDDEN}:
                errors["decision_log"] = (
                    "Only allowed or overridden decisions can issue a permit."
                )
            if self.access_type != log.access_type:
                errors["access_type"] = (
                    "The permit access type must match the clearance decision."
                )
            if self.permit_id and self.permit.student_id != log.student_id:
                errors["permit"] = "The permit and clearance decision must use the same learner."
        if self.status == self.REVOKED:
            if not self.revoked_at:
                errors["revoked_at"] = "Record the revocation time."
            if not self.revocation_reason.strip():
                errors["revocation_reason"] = "Record why the permit was revoked."
        if errors:
            raise ValidationError(errors)
