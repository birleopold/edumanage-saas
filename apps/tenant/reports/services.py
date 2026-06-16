from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db.models import Q

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.assessments.services import grade_for_percentage, percentage, quantize_percent
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.finance.invoicing import invoice_amounts
from apps.tenant.finance.models import Invoice, Payment
from apps.tenant.parents.models import ParentProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


@dataclass(frozen=True)
class SchoolDashboardSummary:
    students_total: int
    students_active: int
    teachers_total: int
    parents_total: int
    active_enrollments: int
    course_offerings: int
    attendance_rate: Decimal | None
    total_billed: Decimal
    total_paid: Decimal
    total_balance: Decimal
    academic_average: Decimal | None
    academic_grade: str
    academic_remark: str


@dataclass(frozen=True)
class FinanceReport:
    invoice_count: int
    paid_count: int
    partial_count: int
    overdue_count: int
    unpaid_count: int
    total_billed: Decimal
    total_paid: Decimal
    total_balance: Decimal
    payments_count: int
    payments_in_range: Decimal
    by_method: list[dict]
    top_debtors: list[dict]
    recent_payments: list[Payment]


@dataclass(frozen=True)
class AttendanceReport:
    session_count: int
    entry_count: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_rate: Decimal | None
    by_offering: list[dict]
    frequent_absentees: list[dict]


@dataclass(frozen=True)
class AcademicPerformanceReport:
    assessment_count: int
    published_assessment_count: int
    score_count: int
    average_percentage: Decimal | None
    overall_grade: str
    overall_remark: str
    by_offering: list[dict]
    student_averages: list[dict]


def _offering_campus_q(campus_id: int):
    return Q(campus_id=campus_id) | Q(campus__isnull=True, class_group__campus_id=campus_id)


def _entry_campus_q(campus_id: int):
    return Q(session__offering__campus_id=campus_id) | Q(
        session__offering__campus__isnull=True,
        session__offering__class_group__campus_id=campus_id,
    )


def _assessment_campus_q(campus_id: int):
    return Q(offering__campus_id=campus_id) | Q(
        offering__campus__isnull=True,
        offering__class_group__campus_id=campus_id,
    )


def _score_campus_q(campus_id: int):
    return Q(assessment__offering__campus_id=campus_id) | Q(
        assessment__offering__campus__isnull=True,
        assessment__offering__class_group__campus_id=campus_id,
    )


def _safe_rate(numerator: int | Decimal, denominator: int | Decimal) -> Decimal | None:
    denominator_dec = Decimal(str(denominator or 0))
    if denominator_dec <= 0:
        return None
    numerator_dec = Decimal(str(numerator or 0))
    return quantize_percent((numerator_dec / denominator_dec) * Decimal("100"))


def _invoice_queryset(campus_id: int | None = None, date_range: DateRange | None = None):
    qs = Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments")
    if campus_id:
        qs = qs.filter(student__campus_id=campus_id)
    if date_range:
        qs = qs.filter(created_at__date__range=(date_range.start, date_range.end))
    return qs


def _payment_queryset(campus_id: int | None = None, date_range: DateRange | None = None):
    qs = Payment.objects.select_related("invoice", "invoice__student")
    if campus_id:
        qs = qs.filter(invoice__student__campus_id=campus_id)
    if date_range:
        qs = qs.filter(received_at__range=(date_range.start, date_range.end))
    return qs


def _attendance_entries(campus_id: int | None = None, date_range: DateRange | None = None):
    qs = AttendanceEntry.objects.select_related(
        "session",
        "session__offering",
        "session__offering__course",
        "session__offering__class_group",
        "student",
    )
    if date_range:
        qs = qs.filter(session__date__range=(date_range.start, date_range.end))
    if campus_id:
        qs = qs.filter(_entry_campus_q(campus_id))
    return qs


def _attendance_sessions(campus_id: int | None = None, date_range: DateRange | None = None):
    qs = AttendanceSession.objects.select_related("offering", "offering__course", "offering__class_group")
    if date_range:
        qs = qs.filter(date__range=(date_range.start, date_range.end))
    if campus_id:
        qs = qs.filter(
            Q(offering__campus_id=campus_id)
            | Q(offering__campus__isnull=True, offering__class_group__campus_id=campus_id)
        )
    return qs


def _assessment_queryset(campus_id: int | None = None, date_range: DateRange | None = None):
    qs = Assessment.objects.select_related("offering", "offering__course", "offering__class_group", "offering__teacher")
    if campus_id:
        qs = qs.filter(_assessment_campus_q(campus_id))
    if date_range:
        qs = qs.filter(Q(date__range=(date_range.start, date_range.end)) | Q(date__isnull=True, created_at__date__range=(date_range.start, date_range.end)))
    return qs


def _score_queryset(campus_id: int | None = None, date_range: DateRange | None = None):
    qs = AssessmentScore.objects.select_related(
        "assessment",
        "assessment__offering",
        "assessment__offering__course",
        "assessment__offering__class_group",
        "student",
    )
    if campus_id:
        qs = qs.filter(_score_campus_q(campus_id))
    if date_range:
        qs = qs.filter(
            Q(assessment__date__range=(date_range.start, date_range.end))
            | Q(assessment__date__isnull=True, assessment__created_at__date__range=(date_range.start, date_range.end))
        )
    return qs


def finance_report(campus_id: int | None, date_range: DateRange) -> FinanceReport:
    invoices = list(_invoice_queryset(campus_id=campus_id, date_range=date_range))
    payments = list(_payment_queryset(campus_id=campus_id, date_range=date_range).order_by("-received_at", "-created_at"))

    total_billed = Decimal("0")
    total_paid = Decimal("0")
    total_balance = Decimal("0")
    paid_count = partial_count = overdue_count = unpaid_count = 0
    debtor_rows = []

    for invoice in invoices:
        amounts = invoice_amounts(invoice)
        total_billed += amounts.total_amount
        total_paid += amounts.total_paid
        total_balance += amounts.balance
        if amounts.display_status == "PAID":
            paid_count += 1
        elif amounts.display_status == "PARTIAL":
            partial_count += 1
        elif amounts.display_status == "OVERDUE":
            overdue_count += 1
        elif amounts.balance > 0:
            unpaid_count += 1
        if amounts.balance > 0:
            debtor_rows.append({"student": invoice.student, "invoice": invoice, "balance": amounts.balance, "due_date": invoice.due_date})

    method_totals: dict[str, dict] = {}
    payments_in_range = Decimal("0")
    for payment in payments:
        payments_in_range += payment.amount or Decimal("0")
        bucket = method_totals.setdefault(payment.method, {"method": payment.get_method_display(), "count": 0, "amount": Decimal("0")})
        bucket["count"] += 1
        bucket["amount"] += payment.amount or Decimal("0")

    return FinanceReport(
        invoice_count=len(invoices),
        paid_count=paid_count,
        partial_count=partial_count,
        overdue_count=overdue_count,
        unpaid_count=unpaid_count,
        total_billed=total_billed,
        total_paid=total_paid,
        total_balance=total_balance,
        payments_count=len(payments),
        payments_in_range=payments_in_range,
        by_method=sorted(method_totals.values(), key=lambda row: row["amount"], reverse=True),
        top_debtors=sorted(debtor_rows, key=lambda row: row["balance"], reverse=True)[:20],
        recent_payments=payments[:20],
    )


def attendance_report(campus_id: int | None, date_range: DateRange) -> AttendanceReport:
    sessions = list(_attendance_sessions(campus_id=campus_id, date_range=date_range))
    entries = list(_attendance_entries(campus_id=campus_id, date_range=date_range))

    present_count = sum(1 for entry in entries if entry.status == AttendanceEntry.PRESENT)
    absent_count = sum(1 for entry in entries if entry.status == AttendanceEntry.ABSENT)
    late_count = sum(1 for entry in entries if entry.status == AttendanceEntry.LATE)
    excused_count = sum(1 for entry in entries if entry.status == AttendanceEntry.EXCUSED)
    attendance_rate = _safe_rate(present_count + late_count + excused_count, len(entries))

    by_offering_map: dict[int, dict] = {}
    absentee_map: dict[int, dict] = {}

    for entry in entries:
        offering = entry.session.offering
        row = by_offering_map.setdefault(
            offering.pk,
            {"offering": offering, "entries": 0, "present": 0, "absent": 0, "late": 0, "excused": 0, "rate": None},
        )
        row["entries"] += 1
        if entry.status == AttendanceEntry.PRESENT:
            row["present"] += 1
        elif entry.status == AttendanceEntry.ABSENT:
            row["absent"] += 1
        elif entry.status == AttendanceEntry.LATE:
            row["late"] += 1
        elif entry.status == AttendanceEntry.EXCUSED:
            row["excused"] += 1

        if entry.status in {AttendanceEntry.ABSENT, AttendanceEntry.LATE}:
            st_row = absentee_map.setdefault(
                entry.student_id,
                {"student": entry.student, "absent": 0, "late": 0, "total_flags": 0},
            )
            if entry.status == AttendanceEntry.ABSENT:
                st_row["absent"] += 1
            else:
                st_row["late"] += 1
            st_row["total_flags"] += 1

    by_offering = []
    for row in by_offering_map.values():
        row["rate"] = _safe_rate(row["present"] + row["late"] + row["excused"], row["entries"])
        by_offering.append(row)

    return AttendanceReport(
        session_count=len(sessions),
        entry_count=len(entries),
        present_count=present_count,
        absent_count=absent_count,
        late_count=late_count,
        excused_count=excused_count,
        attendance_rate=attendance_rate,
        by_offering=sorted(by_offering, key=lambda row: (row["rate"] is None, row["rate"] or Decimal("0")))[:30],
        frequent_absentees=sorted(absentee_map.values(), key=lambda row: row["total_flags"], reverse=True)[:30],
    )


def academic_performance_report(campus_id: int | None, date_range: DateRange) -> AcademicPerformanceReport:
    assessments = list(_assessment_queryset(campus_id=campus_id, date_range=date_range))
    scores = list(_score_queryset(campus_id=campus_id, date_range=date_range).filter(assessment__is_published=True))

    by_offering_map: dict[int, dict] = {}
    by_student_map: dict[int, dict] = {}
    percentages: list[Decimal] = []

    for score in scores:
        pct = percentage(score.score, score.assessment.max_score)
        if pct is None:
            continue
        percentages.append(pct)

        offering = score.assessment.offering
        row = by_offering_map.setdefault(offering.pk, {"offering": offering, "count": 0, "total": Decimal("0"), "average": None, "grade": "-", "remark": "Not graded"})
        row["count"] += 1
        row["total"] += pct

        st_row = by_student_map.setdefault(score.student_id, {"student": score.student, "count": 0, "total": Decimal("0"), "average": None, "grade": "-", "remark": "Not graded"})
        st_row["count"] += 1
        st_row["total"] += pct

    for row in by_offering_map.values():
        row["average"] = quantize_percent(row["total"] / Decimal(row["count"])) if row["count"] else None
        row["grade"], row["remark"] = grade_for_percentage(row["average"])

    for row in by_student_map.values():
        row["average"] = quantize_percent(row["total"] / Decimal(row["count"])) if row["count"] else None
        row["grade"], row["remark"] = grade_for_percentage(row["average"])

    average_percentage = None
    if percentages:
        average_percentage = quantize_percent(sum(percentages, Decimal("0")) / Decimal(len(percentages)))
    overall_grade, overall_remark = grade_for_percentage(average_percentage)

    return AcademicPerformanceReport(
        assessment_count=len(assessments),
        published_assessment_count=sum(1 for assessment in assessments if assessment.is_published),
        score_count=len(scores),
        average_percentage=average_percentage,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        by_offering=sorted(by_offering_map.values(), key=lambda row: (row["average"] is None, row["average"] or Decimal("0")), reverse=True)[:30],
        student_averages=sorted(by_student_map.values(), key=lambda row: (row["average"] is None, row["average"] or Decimal("0")), reverse=True)[:30],
    )


def school_dashboard_summary(campus_id: int | None, date_range: DateRange) -> SchoolDashboardSummary:
    students_qs = StudentProfile.objects.all()
    teachers_qs = TeacherProfile.objects.all()
    enrollment_qs = Enrollment.objects.all()
    offerings_qs = CourseOffering.objects.filter(is_active=True)

    if campus_id:
        students_qs = students_qs.filter(campus_id=campus_id)
        teachers_qs = teachers_qs.filter(campus_id=campus_id)
        enrollment_qs = enrollment_qs.filter(campus_id=campus_id)
        offerings_qs = offerings_qs.filter(_offering_campus_q(campus_id))
        parents_total = ParentProfile.objects.filter(parentstudentlink__student__campus_id=campus_id).distinct().count()
    else:
        parents_total = ParentProfile.objects.count()

    finance = finance_report(campus_id, date_range)
    attendance = attendance_report(campus_id, date_range)
    academics = academic_performance_report(campus_id, date_range)

    return SchoolDashboardSummary(
        students_total=students_qs.count(),
        students_active=students_qs.filter(is_active=True).count(),
        teachers_total=teachers_qs.count(),
        parents_total=parents_total,
        active_enrollments=enrollment_qs.filter(status=Enrollment.ACTIVE).count(),
        course_offerings=offerings_qs.count(),
        attendance_rate=attendance.attendance_rate,
        total_billed=finance.total_billed,
        total_paid=finance.total_paid,
        total_balance=finance.total_balance,
        academic_average=academics.average_percentage,
        academic_grade=academics.overall_grade,
        academic_remark=academics.overall_remark,
    )
