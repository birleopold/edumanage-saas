from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.tenant.assessments.models import AssessmentScore
from apps.tenant.attendance.models import AttendanceEntry
from apps.tenant.coursework.models import Assignment, AssignmentSubmission
from apps.tenant.discipline.models import Incident
from apps.tenant.finance.models import Invoice
from apps.tenant.students.models import StudentProfile


@dataclass(frozen=True)
class RiskSignal:
    key: str
    label: str
    severity: str
    detail: str
    points: int


@dataclass(frozen=True)
class RiskRadarRow:
    student: StudentProfile
    score: int
    level: str
    signals: list[RiskSignal]
    attendance_rate: int | None
    fee_balance: Decimal
    missing_coursework: int
    discipline_count: int
    assessment_average: Decimal | None
    detail_url: str


def _attendance_rate(student: StudentProfile, start, end) -> int | None:
    qs = AttendanceEntry.objects.filter(student=student, session__date__gte=start, session__date__lte=end)
    total = qs.count()
    if not total:
        return None
    present_like = qs.filter(status__in=[AttendanceEntry.PRESENT, AttendanceEntry.LATE, AttendanceEntry.EXCUSED]).count()
    return round((present_like / total) * 100)


def _fee_balance(student: StudentProfile) -> Decimal:
    total = Decimal("0")
    for invoice in Invoice.objects.filter(student=student, status=Invoice.ACTIVE).prefetch_related("lines", "payments", "adjustments"):
        balance = invoice.balance()
        if balance > 0:
            total += balance
    return total


def _missing_coursework(student: StudentProfile, since) -> int:
    if not student.stream_id:
        return 0
    assignments = Assignment.objects.filter(
        is_active=True,
        due_date__lt=timezone.now(),
    ).filter(
        offering__enrollment__student=student,
        offering__enrollment__status="ACTIVE",
    ).distinct()
    submitted_ids = AssignmentSubmission.objects.filter(
        student=student,
        assignment__in=assignments,
        submitted_at__isnull=False,
    ).values_list("assignment_id", flat=True)
    return assignments.exclude(id__in=submitted_ids).filter(due_date__gte=since).count()


def _assessment_average(student: StudentProfile, since) -> Decimal | None:
    scores = AssessmentScore.objects.filter(
        student=student,
        graded_at__gte=since,
        score__isnull=False,
        assessment__max_score__gt=0,
    ).select_related("assessment")
    percentages: list[Decimal] = []
    for score in scores:
        percentages.append((score.score / score.assessment.max_score) * Decimal("100"))
    if not percentages:
        return None
    return sum(percentages, Decimal("0")) / Decimal(len(percentages))


def _discipline_count(student: StudentProfile, since) -> int:
    return Incident.objects.filter(student=student, created_at__gte=since).exclude(status=Incident.DISMISSED).count()


def _risk_level(score: int) -> str:
    if score >= 9:
        return "CRITICAL"
    if score >= 6:
        return "HIGH"
    if score >= 3:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "CLEAR"


def build_student_risk_radar(limit: int = 50, campus_id: int | None = None) -> list[RiskRadarRow]:
    today = timezone.localdate()
    recent_start = today - timedelta(days=14)
    previous_start = today - timedelta(days=28)
    activity_start = timezone.now() - timedelta(days=45)

    students = StudentProfile.objects.filter(is_active=True).select_related("campus", "stream", "stream__class_group")
    if campus_id:
        students = students.filter(campus_id=campus_id)

    rows: list[RiskRadarRow] = []
    for student in students:
        signals: list[RiskSignal] = []

        recent_attendance = _attendance_rate(student, recent_start, today)
        previous_attendance = _attendance_rate(student, previous_start, recent_start - timedelta(days=1))
        if recent_attendance is not None and recent_attendance < 75:
            signals.append(RiskSignal("attendance_low", "Attendance drop", "HIGH", f"{recent_attendance}% attendance in the last 14 days", 3))
        elif recent_attendance is not None and previous_attendance is not None and recent_attendance <= previous_attendance - 15:
            signals.append(RiskSignal("attendance_decline", "Attendance decline", "MEDIUM", f"Dropped from {previous_attendance}% to {recent_attendance}%", 2))

        balance = _fee_balance(student)
        if balance > 0:
            signals.append(RiskSignal("fees", "Overdue fees", "MEDIUM", f"Outstanding balance {balance}", 2))

        assessment_avg = _assessment_average(student, activity_start)
        if assessment_avg is not None and assessment_avg < Decimal("50"):
            signals.append(RiskSignal("assessment", "Poor assessment trend", "HIGH", f"Recent average {assessment_avg:.1f}", 3))

        incidents = _discipline_count(student, activity_start)
        if incidents:
            signals.append(RiskSignal("discipline", "Discipline records", "MEDIUM", f"{incidents} recent incident(s)", 2))

        missing = _missing_coursework(student, activity_start)
        if missing:
            signals.append(RiskSignal("coursework", "Missing coursework", "MEDIUM", f"{missing} overdue assignment(s)", 2))

        score = sum(signal.points for signal in signals)
        if score:
            rows.append(
                RiskRadarRow(
                    student=student,
                    score=score,
                    level=_risk_level(score),
                    signals=signals,
                    attendance_rate=recent_attendance,
                    fee_balance=balance,
                    missing_coursework=missing,
                    discipline_count=incidents,
                    assessment_average=assessment_avg,
                    detail_url=reverse("admin_analytics_student_detail", args=[student.id]),
                )
            )

    return sorted(rows, key=lambda row: (row.score, row.discipline_count, row.missing_coursework), reverse=True)[:limit]
