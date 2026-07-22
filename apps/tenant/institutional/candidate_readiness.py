from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.tenant.finance.clearance_models import (
    ClearanceDecisionLog,
    ClearancePolicy,
)
from apps.tenant.finance.clearance_services import (
    evaluate_clearance,
    record_clearance_decision,
)


class CandidateReadinessReview(models.Model):
    READY = "READY"
    BLOCKED = "BLOCKED"
    REVIEW_CHOICES = (
        (READY, "Ready"),
        (BLOCKED, "Blocked"),
    )

    dossier = models.OneToOneField(
        "institutional.CandidateDossier",
        on_delete=models.CASCADE,
        related_name="readiness_review",
    )
    status = models.CharField(
        max_length=16,
        choices=REVIEW_CHOICES,
        default=BLOCKED,
    )
    target_status = models.CharField(max_length=16)
    checklist_complete = models.BooleanField(default=False)
    photograph_complete = models.BooleanField(default=False)
    continuous_assessment_complete = models.BooleanField(default=False)
    subject_registration_complete = models.BooleanField(default=False)
    finance_clearance_complete = models.BooleanField(default=False)
    clearance_log = models.ForeignKey(
        "finance.ClearanceDecisionLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_readiness_reviews",
    )
    blockers = models.JSONField(default=list, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_readiness_reviews_completed",
    )
    reviewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-reviewed_at",)

    def __str__(self):
        return f"{self.dossier} — {self.get_status_display()}"

    def clean(self):
        super().clean()
        ready = all(
            (
                self.checklist_complete,
                self.photograph_complete,
                self.continuous_assessment_complete,
                self.subject_registration_complete,
                self.finance_clearance_complete,
            )
        )
        if self.status == self.READY and not ready:
            raise ValidationError(
                {"status": "Every candidate readiness requirement must be complete."}
            )


@dataclass(frozen=True)
class CandidateReadinessDecision:
    dossier: object
    target_status: str
    allowed: bool
    blockers: list[str]
    checklist_complete: bool
    photograph_complete: bool
    continuous_assessment_complete: bool
    subject_registration_complete: bool
    clearance_decision: object
    academic_term: object | None


def candidate_term(dossier):
    session = dossier.external_session
    if session.linked_exam_id:
        return session.linked_exam.term
    return None


def required_access_type(target_status):
    if target_status in {
        "SUBMITTED",
        "APPROVED",
    }:
        return ClearancePolicy.EXTERNAL_SUBMISSION
    return ClearancePolicy.CANDIDATE_REGISTRATION


def subject_registration_is_complete(dossier):
    external_candidate = (
        dossier.external_session.candidates.filter(student=dossier.student)
        .prefetch_related("subject_registrations")
        .first()
    )
    if external_candidate is None:
        return False
    active_subject_count = dossier.external_session.subjects.filter(
        is_active=True
    ).count()
    registered_count = external_candidate.subject_registrations.filter(
        status__in=("REGISTERED", "APPROVED"),
    ).count()
    compulsory_count = dossier.external_session.subjects.filter(
        is_active=True,
        is_compulsory=True,
    ).count()
    compulsory_registered = external_candidate.subject_registrations.filter(
        subject__is_compulsory=True,
        subject__is_active=True,
        status__in=("REGISTERED", "APPROVED"),
    ).count()
    return bool(
        registered_count > 0
        and compulsory_registered == compulsory_count
        and registered_count <= active_subject_count
    )


def evaluate_candidate_readiness(dossier, *, target_status=None):
    target_status = target_status or dossier.registration_status
    checklist_complete = dossier.checklist_complete
    photograph_complete = bool(dossier.photograph)
    continuous_assessment_complete = bool(
        dossier.continuous_assessment_complete
    )
    subject_registration_complete = subject_registration_is_complete(dossier)
    term = candidate_term(dossier)
    clearance_decision = evaluate_clearance(
        dossier.student,
        required_access_type(target_status),
        academic_term=term,
    )
    finance_clearance_complete = bool(
        clearance_decision.allowed and not clearance_decision.advisory
    )
    blockers = []
    if not photograph_complete:
        blockers.append("Candidate photograph is missing.")
    if not checklist_complete:
        blockers.append("Candidate document checklist is incomplete.")
    if not continuous_assessment_complete:
        blockers.append("Continuous assessment is incomplete.")
    if not subject_registration_complete:
        blockers.append(
            "External candidate and compulsory subject registration are incomplete."
        )
    if not finance_clearance_complete:
        blockers.append(clearance_decision.message)
    return CandidateReadinessDecision(
        dossier=dossier,
        target_status=target_status,
        allowed=not blockers,
        blockers=blockers,
        checklist_complete=checklist_complete,
        photograph_complete=photograph_complete,
        continuous_assessment_complete=continuous_assessment_complete,
        subject_registration_complete=subject_registration_complete,
        clearance_decision=clearance_decision,
        academic_term=term,
    )


def assert_candidate_readiness(dossier, *, target_status=None):
    decision = evaluate_candidate_readiness(
        dossier,
        target_status=target_status,
    )
    if not decision.allowed:
        raise ValidationError(
            {"registration_status": decision.blockers}
        )
    return decision


def record_candidate_readiness(dossier, *, actor=None, target_status=None):
    decision = evaluate_candidate_readiness(
        dossier,
        target_status=target_status,
    )
    clearance_log = record_clearance_decision(
        decision.clearance_decision,
        source=ClearanceDecisionLog.CANDIDATE,
        checked_by=actor,
    )
    finance_complete = bool(
        decision.clearance_decision.allowed
        and not decision.clearance_decision.advisory
    )
    review, _ = CandidateReadinessReview.objects.update_or_create(
        dossier=dossier,
        defaults={
            "status": (
                CandidateReadinessReview.READY
                if decision.allowed
                else CandidateReadinessReview.BLOCKED
            ),
            "target_status": decision.target_status,
            "checklist_complete": decision.checklist_complete,
            "photograph_complete": decision.photograph_complete,
            "continuous_assessment_complete": (
                decision.continuous_assessment_complete
            ),
            "subject_registration_complete": (
                decision.subject_registration_complete
            ),
            "finance_clearance_complete": finance_complete,
            "clearance_log": clearance_log,
            "blockers": decision.blockers,
            "snapshot": {
                "dossier_id": dossier.pk,
                "student_id": dossier.student_id,
                "external_session_id": dossier.external_session_id,
                "candidate_number": dossier.candidate_number,
                "target_status": decision.target_status,
                "clearance_access_type": (
                    decision.clearance_decision.access_type
                ),
                "clearance_decision": (
                    decision.clearance_decision.decision_code
                ),
                "clearance_reason": decision.clearance_decision.reason,
                "reviewed_at": timezone.now().isoformat(),
            },
            "reviewed_by": actor,
            "reviewed_at": timezone.now(),
        },
    )
    review.full_clean()
    review.save()
    return review
