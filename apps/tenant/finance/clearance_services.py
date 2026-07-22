from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm
from apps.tenant.education_frameworks.models import LevelStageMapping

from .clearance_models import (
    ClearanceDecisionLog,
    ClearanceOverride,
    ClearancePolicy,
    normalize_clearance_code,
)
from .models import Invoice


MONEY_ZERO = Decimal("0.00")
PERCENT_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class FinanceSummary:
    invoice_count: int
    invoiced_amount: Decimal
    paid_amount: Decimal
    outstanding_balance: Decimal
    paid_percentage: Decimal
    academic_term: object | None


@dataclass(frozen=True)
class ClearanceDecision:
    student: object
    access_type: str
    academic_term: object | None
    policy: ClearancePolicy | None
    override: ClearanceOverride | None
    finance: FinanceSummary
    allowed: bool
    advisory: bool
    decision_code: str
    reason: str

    @property
    def blocked(self) -> bool:
        return not self.allowed

    @property
    def message(self) -> str:
        if self.policy and self.policy.user_message:
            return self.policy.user_message
        return self.reason


def current_academic_term():
    return (
        AcademicTerm.objects.filter(is_current=True)
        .select_related("year")
        .order_by("-year__name", "order")
        .first()
    )


def student_scope(student):
    class_group = getattr(getattr(student, "stream", None), "class_group", None)
    level = getattr(class_group, "level", None)
    program = getattr(class_group, "program", None)
    campus = getattr(student, "campus", None) or getattr(class_group, "campus", None)
    stage = None
    if level:
        mapping = (
            LevelStageMapping.objects.filter(legacy_level_id=level.pk)
            .select_related("stage")
            .order_by("-updated_at", "-pk")
            .first()
        )
        if mapping:
            stage = mapping.stage
    return {
        "campus": campus,
        "stage": stage,
        "level": level,
        "program": program,
    }


def policy_is_valid(policy: ClearancePolicy) -> bool:
    try:
        policy.full_clean()
    except ValidationError:
        return False
    return True


def _specificity(policy: ClearancePolicy) -> int:
    return sum(
        bool(value)
        for value in (
            policy.campus_id,
            policy.stage_id,
            policy.level_id,
            policy.program_id,
            policy.academic_term_id,
        )
    )


def resolve_clearance_policy(student, access_type: str, academic_term=None):
    term = academic_term or current_academic_term()
    scope = student_scope(student)
    qs = ClearancePolicy.objects.filter(
        is_active=True,
        access_type=access_type,
    ).select_related(
        "campus",
        "stage",
        "level",
        "program",
        "academic_term",
        "academic_term__year",
    )
    qs = qs.filter(Q(campus__isnull=True) | Q(campus=scope["campus"]))
    qs = qs.filter(Q(stage__isnull=True) | Q(stage=scope["stage"]))
    qs = qs.filter(Q(level__isnull=True) | Q(level=scope["level"]))
    qs = qs.filter(Q(program__isnull=True) | Q(program=scope["program"]))
    if term:
        qs = qs.filter(Q(academic_term__isnull=True) | Q(academic_term=term))
    else:
        qs = qs.filter(academic_term__isnull=True)

    candidates = [policy for policy in qs if policy_is_valid(policy)]
    candidates.sort(
        key=lambda policy: (
            policy.priority,
            _specificity(policy),
            policy.pk,
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None


def finance_summary_for_policy(
    student,
    policy: ClearancePolicy | None,
    academic_term=None,
) -> FinanceSummary:
    term = (
        academic_term
        or (policy.academic_term if policy and policy.academic_term_id else None)
        or current_academic_term()
    )
    invoices = Invoice.objects.filter(student=student).prefetch_related(
        "lines",
        "payments",
    )
    if policy and policy.calculation_basis == ClearancePolicy.ALL_OPEN:
        invoices = invoices.filter(status=Invoice.ACTIVE)
    else:
        if term:
            invoices = invoices.filter(academic_term=term)
        else:
            invoices = invoices.none()

    invoiced = MONEY_ZERO
    paid = MONEY_ZERO
    count = 0
    for invoice in invoices:
        count += 1
        invoiced += invoice.total_amount()
        paid += invoice.total_paid()
    balance = invoiced - paid
    if invoiced > 0:
        percentage = (
            paid * Decimal("100") / invoiced
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        percentage = Decimal("100.00") if count else PERCENT_ZERO
    return FinanceSummary(
        invoice_count=count,
        invoiced_amount=invoiced.quantize(Decimal("0.01")),
        paid_amount=paid.quantize(Decimal("0.01")),
        outstanding_balance=balance.quantize(Decimal("0.01")),
        paid_percentage=percentage,
        academic_term=term,
    )


def resolve_clearance_override(
    student,
    access_type: str,
    policy=None,
    academic_term=None,
):
    day = timezone.localdate()
    qs = ClearanceOverride.objects.filter(
        student=student,
        is_active=True,
        valid_from__lte=day,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=day))
    qs = qs.filter(
        Q(access_type=ClearanceOverride.ALL) | Q(access_type=access_type)
    )
    if academic_term:
        qs = qs.filter(
            Q(academic_term__isnull=True) | Q(academic_term=academic_term)
        )
    else:
        qs = qs.filter(academic_term__isnull=True)
    if policy:
        qs = qs.filter(Q(policy__isnull=True) | Q(policy=policy))
    else:
        qs = qs.filter(policy__isnull=True)
    return (
        qs.select_related("policy", "academic_term", "approved_by")
        .order_by("-valid_until", "-created_at")
        .first()
    )


def _rule_passes(policy: ClearancePolicy, summary: FinanceSummary) -> bool:
    if summary.invoice_count == 0:
        return policy.allow_when_no_invoice
    if policy.rule_type == ClearancePolicy.FULL_PAYMENT:
        return summary.outstanding_balance <= MONEY_ZERO
    if policy.rule_type == ClearancePolicy.MINIMUM_PERCENTAGE:
        return summary.paid_percentage >= policy.minimum_paid_percentage
    if policy.rule_type == ClearancePolicy.MINIMUM_PAID_AMOUNT:
        return summary.paid_amount >= policy.minimum_paid_amount
    if policy.rule_type == ClearancePolicy.MAXIMUM_BALANCE:
        return summary.outstanding_balance <= policy.maximum_outstanding_balance
    return True


def _failure_reason(policy: ClearancePolicy, summary: FinanceSummary) -> str:
    if summary.invoice_count == 0:
        return "No invoice was found for the selected clearance period."
    if policy.rule_type == ClearancePolicy.FULL_PAYMENT:
        return (
            f"Outstanding balance is {summary.outstanding_balance}; "
            "full payment is required."
        )
    if policy.rule_type == ClearancePolicy.MINIMUM_PERCENTAGE:
        return (
            f"Paid percentage is {summary.paid_percentage}%; "
            f"the required minimum is {policy.minimum_paid_percentage}%."
        )
    if policy.rule_type == ClearancePolicy.MINIMUM_PAID_AMOUNT:
        return (
            f"Amount paid is {summary.paid_amount}; "
            f"the required minimum is {policy.minimum_paid_amount}."
        )
    if policy.rule_type == ClearancePolicy.MAXIMUM_BALANCE:
        return (
            f"Outstanding balance is {summary.outstanding_balance}; "
            f"the permitted maximum is {policy.maximum_outstanding_balance}."
        )
    return "The learner does not meet the configured finance-clearance rule."


def evaluate_clearance(
    student,
    access_type: str,
    academic_term=None,
) -> ClearanceDecision:
    term = academic_term or current_academic_term()
    policy = resolve_clearance_policy(
        student,
        access_type,
        academic_term=term,
    )
    summary = finance_summary_for_policy(
        student,
        policy,
        academic_term=term,
    )
    if not policy:
        return ClearanceDecision(
            student=student,
            access_type=access_type,
            academic_term=term,
            policy=None,
            override=None,
            finance=summary,
            allowed=True,
            advisory=False,
            decision_code=ClearanceDecisionLog.ALLOWED,
            reason="No active clearance policy applies; access remains available.",
        )

    override = resolve_clearance_override(
        student,
        access_type,
        policy=policy,
        academic_term=term,
    )
    if override:
        return ClearanceDecision(
            student=student,
            access_type=access_type,
            academic_term=term,
            policy=policy,
            override=override,
            finance=summary,
            allowed=True,
            advisory=False,
            decision_code=ClearanceDecisionLog.OVERRIDDEN,
            reason=(
                f"Access granted by approved {override.get_exception_type_display().lower()}: "
                f"{override.reason}"
            ),
        )

    passed = _rule_passes(policy, summary)
    if passed:
        return ClearanceDecision(
            student=student,
            access_type=access_type,
            academic_term=term,
            policy=policy,
            override=None,
            finance=summary,
            allowed=True,
            advisory=False,
            decision_code=ClearanceDecisionLog.ALLOWED,
            reason="The learner meets the configured finance-clearance rule.",
        )

    reason = _failure_reason(policy, summary)
    advisory = policy.enforcement_mode == ClearancePolicy.ADVISORY
    return ClearanceDecision(
        student=student,
        access_type=access_type,
        academic_term=term,
        policy=policy,
        override=None,
        finance=summary,
        allowed=advisory,
        advisory=advisory,
        decision_code=(
            ClearanceDecisionLog.ADVISED
            if advisory
            else ClearanceDecisionLog.BLOCKED
        ),
        reason=reason,
    )


def record_clearance_decision(
    decision: ClearanceDecision,
    *,
    source=ClearanceDecisionLog.ADMIN,
    checked_by=None,
):
    log = ClearanceDecisionLog.objects.create(
        student=decision.student,
        policy=decision.policy,
        override=decision.override,
        academic_term=decision.academic_term,
        access_type=decision.access_type,
        decision=decision.decision_code,
        source=source,
        invoiced_amount=decision.finance.invoiced_amount,
        paid_amount=decision.finance.paid_amount,
        outstanding_balance=decision.finance.outstanding_balance,
        paid_percentage=decision.finance.paid_percentage,
        reason=decision.reason[:255],
        checked_by=checked_by,
    )
    if (
        decision.allowed
        and not decision.advisory
        and decision.policy
        and decision.policy.issue_permit_on_success
    ):
        from .clearance_permit_services import issue_clearance_permit

        issue_clearance_permit(log, issued_by=checked_by)
    return log


def bootstrap_policy_templates(*, apply=False):
    templates = [
        (ClearancePolicy.ONLINE_EXAM, "Online examination clearance"),
        (ClearancePolicy.PHYSICAL_EXAM, "Physical examination attendance clearance"),
        (ClearancePolicy.ASSESSMENT_RESULTS, "Assessment-results clearance"),
        (ClearancePolicy.ASSESSMENT_REPORT, "Assessment report-card clearance"),
        (ClearancePolicy.EXAM_RESULTS, "Examination-results clearance"),
        (ClearancePolicy.EXAM_REPORT, "Examination report-card clearance"),
        (ClearancePolicy.CANDIDATE_REGISTRATION, "Candidate-registration clearance"),
        (ClearancePolicy.EXTERNAL_SUBMISSION, "External-examination submission clearance"),
        (ClearancePolicy.PERMIT_ISSUANCE, "Clearance-permit issuance"),
    ]
    rows = []
    for access_type, name in templates:
        code = normalize_clearance_code(f"TEMPLATE-{access_type}")
        exists = ClearancePolicy.objects.filter(code=code).exists()
        rows.append(
            {
                "code": code,
                "access_type": access_type,
                "exists": exists,
            }
        )
        if apply and not exists:
            ClearancePolicy.objects.create(
                code=code,
                name=name,
                access_type=access_type,
                calculation_basis=ClearancePolicy.CURRENT_TERM,
                rule_type=ClearancePolicy.FULL_PAYMENT,
                enforcement_mode=ClearancePolicy.ADVISORY,
                allow_when_no_invoice=True,
                user_message=(
                    "Please contact the finance office to confirm your fee clearance."
                ),
                is_active=False,
            )
    return rows


def clearance_readiness():
    policies = list(ClearancePolicy.objects.select_related("academic_term"))
    invalid = [policy for policy in policies if not policy_is_valid(policy)]
    day = timezone.localdate()
    expired_active_overrides = ClearanceOverride.objects.filter(
        is_active=True,
        valid_until__lt=day,
    ).count()
    invalid_overrides = []
    for override in ClearanceOverride.objects.select_related(
        "policy",
        "academic_term",
        "approved_by",
    ):
        try:
            override.full_clean()
        except ValidationError as exc:
            invalid_overrides.append(
                {"override": override, "errors": exc.messages}
            )
    access_types = {
        policy.access_type
        for policy in policies
        if policy.is_active and policy not in invalid
    }
    missing_access_types = [
        code
        for code, _label in ClearancePolicy.ACCESS_TYPE_CHOICES
        if code not in access_types
    ]
    return {
        "policy_count": len(policies),
        "active_policy_count": sum(1 for policy in policies if policy.is_active),
        "invalid_policy_count": len(invalid),
        "invalid_policies": invalid,
        "override_count": ClearanceOverride.objects.count(),
        "invalid_override_count": len(invalid_overrides),
        "invalid_overrides": invalid_overrides,
        "expired_active_override_count": expired_active_overrides,
        "decision_log_count": ClearanceDecisionLog.objects.count(),
        "missing_access_types": missing_access_types,
        "ready": not invalid and not invalid_overrides,
    }
