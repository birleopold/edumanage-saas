from django.contrib import admin

from .clearance_models import (
    ClearanceDecisionLog,
    ClearanceOverride,
    ClearancePolicy,
)
from .clearance_permits import ClearancePermitSnapshot


@admin.register(ClearancePolicy)
class ClearancePolicyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "access_type",
        "rule_type",
        "enforcement_mode",
        "issue_permit_on_success",
        "priority",
        "is_active",
    )
    list_filter = (
        "access_type",
        "rule_type",
        "enforcement_mode",
        "issue_permit_on_success",
        "is_active",
        "campus",
        "stage",
        "level",
        "program",
    )
    search_fields = ("code", "name", "description", "user_message")
    raw_id_fields = ("campus", "stage", "level", "program", "academic_term")


@admin.register(ClearanceOverride)
class ClearanceOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exception_type",
        "access_type",
        "policy",
        "valid_from",
        "valid_until",
        "approved_amount",
        "is_active",
        "approved_by",
    )
    list_filter = (
        "exception_type",
        "access_type",
        "is_active",
        "valid_from",
        "valid_until",
    )
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__student_id",
        "reference",
        "evidence_reference",
        "reason",
    )
    raw_id_fields = ("student", "policy", "academic_term", "approved_by")


@admin.register(ClearanceDecisionLog)
class ClearanceDecisionLogAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "access_type",
        "decision",
        "source",
        "paid_amount",
        "outstanding_balance",
        "paid_percentage",
        "policy",
        "override",
        "created_at",
    )
    list_filter = (
        "access_type",
        "decision",
        "source",
        "created_at",
    )
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__student_id",
        "reason",
        "policy__code",
        "override__reference",
    )
    raw_id_fields = (
        "student",
        "policy",
        "override",
        "academic_term",
        "checked_by",
    )
    readonly_fields = (
        "student",
        "policy",
        "override",
        "academic_term",
        "access_type",
        "decision",
        "source",
        "invoiced_amount",
        "paid_amount",
        "outstanding_balance",
        "paid_percentage",
        "reason",
        "checked_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ClearancePermitSnapshot)
class ClearancePermitSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "permit",
        "access_type",
        "decision",
        "status",
        "paid_amount",
        "outstanding_balance",
        "valid_from",
        "valid_until",
        "issued_by",
        "issued_at",
    )
    list_filter = ("access_type", "decision", "status", "valid_until")
    search_fields = (
        "permit__reference",
        "permit__student__first_name",
        "permit__student__last_name",
        "permit__student__student_id",
        "policy_code",
        "revocation_reason",
    )
    raw_id_fields = (
        "decision_log",
        "permit",
        "issued_by",
        "revoked_by",
    )
    readonly_fields = (
        "decision_log",
        "permit",
        "policy_code",
        "access_type",
        "decision",
        "invoiced_amount",
        "paid_amount",
        "outstanding_balance",
        "paid_percentage",
        "rule_snapshot",
        "override_snapshot",
        "academic_snapshot",
        "valid_from",
        "valid_until",
        "issued_by",
        "issued_at",
    )

    def has_add_permission(self, request):
        return False
