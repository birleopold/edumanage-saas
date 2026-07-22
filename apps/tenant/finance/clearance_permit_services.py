from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant.institutional.models import VerifiablePermit

from .clearance_models import ClearanceDecisionLog, ClearancePolicy
from .clearance_permits import ClearancePermitSnapshot


PERMIT_TITLES = {
    ClearancePolicy.ONLINE_EXAM: "Online Examination Clearance",
    ClearancePolicy.PHYSICAL_EXAM: "Examination Attendance Permit",
    ClearancePolicy.ASSESSMENT_RESULTS: "Assessment Results Clearance",
    ClearancePolicy.ASSESSMENT_REPORT: "Assessment Report Clearance",
    ClearancePolicy.EXAM_RESULTS: "Examination Results Clearance",
    ClearancePolicy.EXAM_REPORT: "Examination Report Clearance",
    ClearancePolicy.CANDIDATE_REGISTRATION: "Candidate Registration Clearance",
    ClearancePolicy.EXTERNAL_SUBMISSION: "External Examination Submission Clearance",
    ClearancePolicy.PERMIT_ISSUANCE: "Examination Clearance Permit",
}


def permit_type_for_access(access_type):
    if access_type in {
        ClearancePolicy.CANDIDATE_REGISTRATION,
        ClearancePolicy.EXTERNAL_SUBMISSION,
        ClearancePolicy.PHYSICAL_EXAM,
    }:
        return VerifiablePermit.CANDIDATE
    return VerifiablePermit.CLEARANCE


def _money(value):
    return str(Decimal(value or 0).quantize(Decimal("0.01")))


def policy_snapshot(policy):
    if policy is None:
        return {}
    return {
        "id": policy.pk,
        "code": policy.code,
        "name": policy.name,
        "access_type": policy.access_type,
        "calculation_basis": policy.calculation_basis,
        "rule_type": policy.rule_type,
        "minimum_paid_percentage": str(policy.minimum_paid_percentage),
        "minimum_paid_amount": str(policy.minimum_paid_amount),
        "maximum_outstanding_balance": str(policy.maximum_outstanding_balance),
        "allow_when_no_invoice": policy.allow_when_no_invoice,
        "enforcement_mode": policy.enforcement_mode,
        "priority": policy.priority,
        "permit_validity_days": policy.permit_validity_days,
    }


def override_snapshot(override):
    if override is None:
        return {}
    return {
        "id": override.pk,
        "exception_type": override.exception_type,
        "access_type": override.access_type,
        "reason": override.reason,
        "reference": override.reference,
        "evidence_reference": override.evidence_reference,
        "approved_amount": (
            str(override.approved_amount)
            if override.approved_amount is not None
            else None
        ),
        "valid_from": override.valid_from.isoformat(),
        "valid_until": (
            override.valid_until.isoformat() if override.valid_until else None
        ),
        "approved_by_id": override.approved_by_id,
    }


def academic_snapshot(log):
    student = log.student
    class_group = getattr(getattr(student, "stream", None), "class_group", None)
    return {
        "student_id": student.pk,
        "student_number": student.student_id,
        "campus_id": student.campus_id,
        "class_group_id": getattr(class_group, "pk", None),
        "level_id": getattr(class_group, "level_id", None),
        "program_id": getattr(class_group, "program_id", None),
        "academic_term_id": log.academic_term_id,
        "academic_term": str(log.academic_term) if log.academic_term_id else "",
    }


@transaction.atomic
def issue_clearance_permit(
    decision_log: ClearanceDecisionLog,
    *,
    issued_by=None,
    force=False,
):
    if decision_log.decision not in {
        ClearanceDecisionLog.ALLOWED,
        ClearanceDecisionLog.OVERRIDDEN,
    }:
        raise ValidationError("A blocked or advisory decision cannot issue a permit.")
    try:
        existing = decision_log.permit_snapshot
    except ClearancePermitSnapshot.DoesNotExist:
        existing = None
    if existing and not force:
        return existing

    policy = decision_log.policy
    validity_days = policy.permit_validity_days if policy else 30
    valid_from = timezone.now()
    valid_until = valid_from + timedelta(days=validity_days)
    reference = f"CLR-{decision_log.student_id}-{decision_log.pk}"
    title = PERMIT_TITLES.get(
        decision_log.access_type,
        "Education Clearance Permit",
    )
    rule = policy_snapshot(policy)
    exception = override_snapshot(decision_log.override)
    academic = academic_snapshot(decision_log)
    frozen = {
        "decision_log_id": decision_log.pk,
        "access_type": decision_log.access_type,
        "decision": decision_log.decision,
        "reason": decision_log.reason,
        "invoiced_amount": _money(decision_log.invoiced_amount),
        "paid_amount": _money(decision_log.paid_amount),
        "outstanding_balance": _money(decision_log.outstanding_balance),
        "paid_percentage": str(decision_log.paid_percentage),
        "policy": rule,
        "override": exception,
        "academic": academic,
        "issued_at": valid_from.isoformat(),
        "valid_until": valid_until.isoformat(),
    }
    permit, _ = VerifiablePermit.objects.update_or_create(
        reference=reference,
        defaults={
            "permit_type": permit_type_for_access(decision_log.access_type),
            "student": decision_log.student,
            "title": title,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "status": VerifiablePermit.ACTIVE,
            "metadata": frozen,
            "approved_by": issued_by or decision_log.checked_by,
        },
    )
    if existing:
        existing.permit = permit
        existing.policy_code = policy.code if policy else ""
        existing.access_type = decision_log.access_type
        existing.decision = decision_log.decision
        existing.invoiced_amount = decision_log.invoiced_amount
        existing.paid_amount = decision_log.paid_amount
        existing.outstanding_balance = decision_log.outstanding_balance
        existing.paid_percentage = decision_log.paid_percentage
        existing.rule_snapshot = rule
        existing.override_snapshot = exception
        existing.academic_snapshot = academic
        existing.status = ClearancePermitSnapshot.ACTIVE
        existing.valid_from = valid_from
        existing.valid_until = valid_until
        existing.issued_by = issued_by or decision_log.checked_by
        existing.revoked_by = None
        existing.revoked_at = None
        existing.revocation_reason = ""
        existing.full_clean()
        existing.save()
        return existing

    snapshot = ClearancePermitSnapshot(
        decision_log=decision_log,
        permit=permit,
        policy_code=policy.code if policy else "",
        access_type=decision_log.access_type,
        decision=decision_log.decision,
        invoiced_amount=decision_log.invoiced_amount,
        paid_amount=decision_log.paid_amount,
        outstanding_balance=decision_log.outstanding_balance,
        paid_percentage=decision_log.paid_percentage,
        rule_snapshot=rule,
        override_snapshot=exception,
        academic_snapshot=academic,
        valid_from=valid_from,
        valid_until=valid_until,
        issued_by=issued_by or decision_log.checked_by,
    )
    snapshot.full_clean()
    snapshot.save()
    return snapshot


@transaction.atomic
def revoke_clearance_permit(snapshot, *, revoked_by=None, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError("Record why the clearance permit is being revoked.")
    now = timezone.now()
    snapshot.status = ClearancePermitSnapshot.REVOKED
    snapshot.revoked_by = revoked_by
    snapshot.revoked_at = now
    snapshot.revocation_reason = reason
    snapshot.permit.status = VerifiablePermit.REVOKED
    snapshot.permit.save(update_fields=["status"])
    snapshot.full_clean()
    snapshot.save()
    return snapshot


def expire_clearance_permits(*, now=None):
    now = now or timezone.now()
    snapshots = ClearancePermitSnapshot.objects.filter(
        status=ClearancePermitSnapshot.ACTIVE,
        valid_until__lt=now,
    ).select_related("permit")
    updated = 0
    for snapshot in snapshots:
        snapshot.status = ClearancePermitSnapshot.EXPIRED
        snapshot.permit.status = VerifiablePermit.EXPIRED
        snapshot.permit.save(update_fields=["status"])
        snapshot.save(update_fields=["status"])
        updated += 1
    return updated
