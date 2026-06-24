from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.admissions.models import AdmissionAppointment, AdmissionLead, Applicant
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.assessments.services import grade_for_percentage, percentage, quantize_percent
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.audit.models import AuditEvent, BackupJob, LoginHistory
from apps.tenant.finance.invoicing import invoice_amounts
from apps.tenant.finance.models import Invoice, Payment
from apps.tenant.hr.models import Payslip, PayrollApproval
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import User

from .services import DateRange, _assessment_campus_q, _entry_campus_q, _safe_rate


@dataclass(frozen=True)
class AdvancedReport:
    title: str
    description: str
    icon: str
    cards: list[dict]
    tables: list[dict]


def _money(value):
    return value or Decimal("0")


def _date_filter(field: str, date_range: DateRange):
    return {f"{field}__date__range": (date_range.start, date_range.end)}


def _safe_percent(numerator, denominator):
    return _safe_rate(numerator, denominator)


def _campus_student_filter(qs, campus_id):
    return qs.filter(campus_id=campus_id) if campus_id else qs


def student_performance_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    scores = AssessmentScore.objects.select_related("assessment", "assessment__offering", "assessment__offering__class_group", "student").filter(
        Q(assessment__date__range=(date_range.start, date_range.end))
        | Q(assessment__date__isnull=True, assessment__created_at__date__range=(date_range.start, date_range.end))
    )
    if campus_id:
        scores = scores.filter(Q(student__campus_id=campus_id) | Q(_assessment_campus_q(campus_id)))

    student_map: dict[int, dict] = {}
    class_map: dict[int, dict] = {}
    percentages = []
    for score in scores:
        pct = percentage(score.score, score.assessment.max_score)
        if pct is None:
            continue
        percentages.append(pct)
        student_row = student_map.setdefault(score.student_id, {"student": score.student, "count": 0, "total": Decimal("0"), "average": None, "grade": "-", "remark": "Not graded"})
        student_row["count"] += 1
        student_row["total"] += pct
        class_group = score.assessment.offering.class_group if score.assessment and score.assessment.offering else None
        class_key = class_group.pk if class_group else 0
        class_row = class_map.setdefault(class_key, {"class_group": class_group or "Unassigned", "count": 0, "total": Decimal("0"), "average": None, "grade": "-", "remark": "Not graded"})
        class_row["count"] += 1
        class_row["total"] += pct

    for row in student_map.values():
        row["average"] = quantize_percent(row["total"] / Decimal(row["count"])) if row["count"] else None
        row["grade"], row["remark"] = grade_for_percentage(row["average"])
    for row in class_map.values():
        row["average"] = quantize_percent(row["total"] / Decimal(row["count"])) if row["count"] else None
        row["grade"], row["remark"] = grade_for_percentage(row["average"])

    overall = quantize_percent(sum(percentages, Decimal("0")) / Decimal(len(percentages))) if percentages else None
    overall_grade, overall_remark = grade_for_percentage(overall)
    at_risk = [row for row in student_map.values() if row["average"] is not None and row["average"] < Decimal("50")]

    return AdvancedReport(
        title="Student Performance Report",
        description="Track published and scored assessments, class averages, top performers and learners needing support.",
        icon="ph-chart-line-up",
        cards=[
            {"label": "Average", "value": f"{overall}%" if overall is not None else "-", "hint": f"{overall_grade} · {overall_remark}"},
            {"label": "Scores", "value": len(percentages), "hint": "Valid scored records"},
            {"label": "Students assessed", "value": len(student_map), "hint": "Unique learners"},
            {"label": "Need support", "value": len(at_risk), "hint": "Average below 50%"},
        ],
        tables=[
            {"title": "Class performance", "headers": ["Class", "Scores", "Average", "Grade", "Remark"], "rows": [[r["class_group"], r["count"], r["average"], r["grade"], r["remark"]] for r in sorted(class_map.values(), key=lambda item: item["average"] or Decimal("0"), reverse=True)[:30]]},
            {"title": "Student performance", "headers": ["Student", "Scores", "Average", "Grade", "Remark"], "rows": [[r["student"], r["count"], r["average"], r["grade"], r["remark"]] for r in sorted(student_map.values(), key=lambda item: item["average"] or Decimal("0"), reverse=True)[:50]]},
        ],
    )


def fee_collection_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    invoices = Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments").filter(created_at__date__range=(date_range.start, date_range.end))
    payments = Payment.objects.select_related("invoice", "invoice__student").filter(received_at__range=(date_range.start, date_range.end))
    if campus_id:
        invoices = invoices.filter(student__campus_id=campus_id)
        payments = payments.filter(invoice__student__campus_id=campus_id)

    total_billed = Decimal("0")
    total_paid_against_invoices = Decimal("0")
    total_balance = Decimal("0")
    invoice_rows = []
    for invoice in invoices:
        amounts = invoice_amounts(invoice)
        total_billed += amounts.total_amount
        total_paid_against_invoices += amounts.total_paid
        total_balance += amounts.balance
        invoice_rows.append([invoice.reference or invoice.id, invoice.student, invoice.total_amount(), invoice.total_paid(), invoice.balance(), invoice.get_status_display()])

    payments_total = sum((_money(p.amount) for p in payments), Decimal("0"))
    collection_rate = _safe_percent(total_paid_against_invoices, total_billed)
    method_rows = []
    for row in payments.values("method").annotate(count=Count("id")):
        method_payments = payments.filter(method=row["method"])
        method_rows.append([row["method"], row["count"], sum((_money(p.amount) for p in method_payments), Decimal("0"))])

    return AdvancedReport(
        title="Fee Collection Report",
        description="Measure billed fees, payments received, collection rate and outstanding balances.",
        icon="ph-wallet",
        cards=[
            {"label": "Total billed", "value": total_billed, "hint": "Invoices in selected period"},
            {"label": "Total paid", "value": total_paid_against_invoices, "hint": "Payments against selected invoices"},
            {"label": "Balance", "value": total_balance, "hint": "Outstanding amount"},
            {"label": "Collection rate", "value": f"{collection_rate}%" if collection_rate is not None else "-", "hint": f"Direct payments in range: {payments_total}"},
        ],
        tables=[
            {"title": "Payment methods", "headers": ["Method", "Count", "Amount"], "rows": method_rows},
            {"title": "Recent invoice balances", "headers": ["Invoice", "Student", "Billed", "Paid", "Balance", "Status"], "rows": invoice_rows[:50]},
        ],
    )


def attendance_summary_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    entries = AttendanceEntry.objects.select_related("session", "session__offering", "session__offering__class_group", "student").filter(session__date__range=(date_range.start, date_range.end))
    if campus_id:
        entries = entries.filter(_entry_campus_q(campus_id))

    total = entries.count()
    present = entries.filter(status=AttendanceEntry.PRESENT).count()
    absent = entries.filter(status=AttendanceEntry.ABSENT).count()
    late = entries.filter(status=AttendanceEntry.LATE).count()
    excused = entries.filter(status=AttendanceEntry.EXCUSED).count()
    rate = _safe_percent(present + late + excused, total)
    class_map = {}
    learner_map = {}
    for entry in entries:
        class_group = entry.session.offering.class_group if entry.session and entry.session.offering else None
        key = class_group.pk if class_group else 0
        class_row = class_map.setdefault(key, {"class_group": class_group or "Unassigned", "entries": 0, "present": 0, "absent": 0, "late": 0, "rate": None})
        class_row["entries"] += 1
        class_row[entry.status.lower()] = class_row.get(entry.status.lower(), 0) + 1
        learner_row = learner_map.setdefault(entry.student_id, {"student": entry.student, "absent": 0, "late": 0, "flags": 0})
        if entry.status == AttendanceEntry.ABSENT:
            learner_row["absent"] += 1
            learner_row["flags"] += 1
        elif entry.status == AttendanceEntry.LATE:
            learner_row["late"] += 1
            learner_row["flags"] += 1
    for row in class_map.values():
        row["rate"] = _safe_percent(row.get("present", 0) + row.get("late", 0), row["entries"])

    return AdvancedReport(
        title="Attendance Report",
        description="Monitor attendance rates, absence patterns and punctuality by class and student.",
        icon="ph-calendar-check",
        cards=[
            {"label": "Attendance rate", "value": f"{rate}%" if rate is not None else "-", "hint": "Present + late + excused"},
            {"label": "Present", "value": present, "hint": "Entries marked present"},
            {"label": "Absent", "value": absent, "hint": "Entries marked absent"},
            {"label": "Late", "value": late, "hint": "Entries marked late"},
        ],
        tables=[
            {"title": "Attendance by class", "headers": ["Class", "Entries", "Present", "Absent", "Late", "Rate"], "rows": [[r["class_group"], r["entries"], r.get("present", 0), r.get("absent", 0), r.get("late", 0), r["rate"]] for r in class_map.values()]},
            {"title": "Frequent absence/late flags", "headers": ["Student", "Absent", "Late", "Total flags"], "rows": [[r["student"], r["absent"], r["late"], r["flags"]] for r in sorted(learner_map.values(), key=lambda item: item["flags"], reverse=True)[:50]]},
        ],
    )


def teacher_workload_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    teachers = TeacherProfile.objects.all()
    offerings = CourseOffering.objects.select_related("teacher", "course", "class_group").filter(is_active=True)
    sessions = AttendanceSession.objects.select_related("offering", "offering__teacher").filter(date__range=(date_range.start, date_range.end))
    assessments = Assessment.objects.select_related("offering", "offering__teacher").filter(created_at__date__range=(date_range.start, date_range.end))
    if campus_id:
        teachers = teachers.filter(campus_id=campus_id)
        offerings = offerings.filter(_assessment_campus_q(campus_id))
        sessions = sessions.filter(Q(offering__campus_id=campus_id) | Q(offering__class_group__campus_id=campus_id))
        assessments = assessments.filter(_assessment_campus_q(campus_id))

    teacher_map = {teacher.pk: {"teacher": teacher, "offerings": 0, "students": 0, "sessions": 0, "assessments": 0, "load_score": 0} for teacher in teachers}
    for offering in offerings:
        if not offering.teacher_id:
            continue
        row = teacher_map.setdefault(offering.teacher_id, {"teacher": offering.teacher, "offerings": 0, "students": 0, "sessions": 0, "assessments": 0, "load_score": 0})
        row["offerings"] += 1
        row["students"] += Enrollment.objects.filter(offering=offering, status=Enrollment.ACTIVE).count()
    for session in sessions:
        teacher_id = session.offering.teacher_id if session.offering else None
        if teacher_id and teacher_id in teacher_map:
            teacher_map[teacher_id]["sessions"] += 1
    for assessment in assessments:
        teacher_id = assessment.offering.teacher_id if assessment.offering else None
        if teacher_id and teacher_id in teacher_map:
            teacher_map[teacher_id]["assessments"] += 1
    for row in teacher_map.values():
        row["load_score"] = row["offerings"] + row["sessions"] + row["assessments"] + row["students"]

    rows = sorted(teacher_map.values(), key=lambda item: item["load_score"], reverse=True)
    return AdvancedReport(
        title="Teacher Workload Report",
        description="Compare teacher load using active course offerings, enrolled learners, attendance sessions and assessments.",
        icon="ph-chalkboard-teacher",
        cards=[
            {"label": "Teachers", "value": len(rows), "hint": "Included in workload view"},
            {"label": "Offerings", "value": sum(r["offerings"] for r in rows), "hint": "Active course assignments"},
            {"label": "Sessions", "value": sum(r["sessions"] for r in rows), "hint": "Attendance sessions"},
            {"label": "Assessments", "value": sum(r["assessments"] for r in rows), "hint": "Created in range"},
        ],
        tables=[{"title": "Teacher workload", "headers": ["Teacher", "Offerings", "Students", "Sessions", "Assessments", "Load score"], "rows": [[r["teacher"], r["offerings"], r["students"], r["sessions"], r["assessments"], r["load_score"]] for r in rows[:60]]}],
    )


def admission_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    applicants = Applicant.objects.select_related("campus", "target_class_group").filter(created_at__date__range=(date_range.start, date_range.end))
    leads = AdmissionLead.objects.select_related("campus").filter(created_at__date__range=(date_range.start, date_range.end))
    appointments = AdmissionAppointment.objects.select_related("applicant").filter(scheduled_at__date__range=(date_range.start, date_range.end))
    if campus_id:
        applicants = applicants.filter(campus_id=campus_id)
        leads = leads.filter(campus_id=campus_id)
        appointments = appointments.filter(applicant__campus_id=campus_id)

    admitted = applicants.filter(status=Applicant.ADMITTED).count()
    conversion = _safe_percent(admitted, applicants.count())
    status_rows = [[item["status"], item["count"]] for item in applicants.values("status").annotate(count=Count("id"))]
    source_rows = [[item["source"], item["count"]] for item in applicants.values("source").annotate(count=Count("id"))]
    lead_rows = [[item["status"], item["count"]] for item in leads.values("status").annotate(count=Count("id"))]

    return AdvancedReport(
        title="Admission Report",
        description="Track admissions funnel performance, application sources, lead status and appointments.",
        icon="ph-user-plus",
        cards=[
            {"label": "Applicants", "value": applicants.count(), "hint": "Created in selected range"},
            {"label": "Admitted", "value": admitted, "hint": "Converted to admission"},
            {"label": "Conversion rate", "value": f"{conversion}%" if conversion is not None else "-", "hint": "Admitted / applicants"},
            {"label": "Appointments", "value": appointments.count(), "hint": "Scheduled in range"},
        ],
        tables=[
            {"title": "Applicants by status", "headers": ["Status", "Count"], "rows": status_rows},
            {"title": "Applicants by source", "headers": ["Source", "Count"], "rows": source_rows},
            {"title": "Leads by status", "headers": ["Lead status", "Count"], "rows": lead_rows},
        ],
    )


def debtor_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    invoices = Invoice.objects.select_related("student").prefetch_related("lines", "payments")
    if campus_id:
        invoices = invoices.filter(student__campus_id=campus_id)
    debtor_rows = []
    total_balance = Decimal("0")
    overdue_count = 0
    for invoice in invoices:
        amounts = invoice_amounts(invoice)
        if amounts.balance <= 0:
            continue
        total_balance += amounts.balance
        if invoice.due_date and invoice.due_date < date_range.end:
            overdue_count += 1
        debtor_rows.append([invoice.student, invoice.reference or invoice.id, invoice.due_date, amounts.total_amount, amounts.total_paid, amounts.balance])
    debtor_rows.sort(key=lambda row: row[-1], reverse=True)
    return AdvancedReport(
        title="Debtor Report",
        description="Identify outstanding balances, overdue accounts and top debtors for follow-up.",
        icon="ph-warning-circle",
        cards=[
            {"label": "Debtor invoices", "value": len(debtor_rows), "hint": "Invoices with balances"},
            {"label": "Total balance", "value": total_balance, "hint": "Outstanding fees"},
            {"label": "Overdue", "value": overdue_count, "hint": "Due before report end date"},
            {"label": "Top debtor", "value": debtor_rows[0][-1] if debtor_rows else 0, "hint": debtor_rows[0][0] if debtor_rows else "No debtors"},
        ],
        tables=[{"title": "Outstanding balances", "headers": ["Student", "Invoice", "Due date", "Billed", "Paid", "Balance"], "rows": debtor_rows[:100]}],
    )


def payroll_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    payslips = Payslip.objects.select_related("staff", "generated_by", "approved_by").filter(generated_at__date__range=(date_range.start, date_range.end))
    approvals = PayrollApproval.objects.select_related("payslip", "approver").filter(created_at__date__range=(date_range.start, date_range.end))
    if campus_id:
        payslips = payslips.filter(staff__campus_id=campus_id)
        approvals = approvals.filter(payslip__staff__campus_id=campus_id)
    gross = sum((_money(item.gross_salary) for item in payslips), Decimal("0"))
    deductions = sum((_money(item.total_deductions) for item in payslips), Decimal("0"))
    net = sum((_money(item.net_salary) for item in payslips), Decimal("0"))
    status_rows = [[item["status"], item["count"]] for item in payslips.values("status").annotate(count=Count("id"))]
    rows = [[p.staff, p.period_year, p.period_month, p.gross_salary, p.total_deductions, p.net_salary, p.get_status_display(), p.approved_by, p.approved_at] for p in payslips[:100]]
    return AdvancedReport(
        title="Payroll Report",
        description="Review payroll totals, deductions, net pay, payslip status and approval progress.",
        icon="ph-bank",
        cards=[
            {"label": "Payslips", "value": payslips.count(), "hint": "Generated in selected period"},
            {"label": "Gross pay", "value": gross, "hint": "Before deductions"},
            {"label": "Deductions", "value": deductions, "hint": "Total deductions"},
            {"label": "Net pay", "value": net, "hint": f"Approvals: {approvals.count()}"},
        ],
        tables=[
            {"title": "Payslip status", "headers": ["Status", "Count"], "rows": status_rows},
            {"title": "Payroll details", "headers": ["Staff", "Year", "Month", "Gross", "Deductions", "Net", "Status", "Approved by", "Approved at"], "rows": rows},
        ],
    )


def tenant_usage_report(campus_id: int | None, date_range: DateRange) -> AdvancedReport:
    users = User.objects.filter(is_active=True)
    events = AuditEvent.objects.select_related("user", "campus").filter(created_at__date__range=(date_range.start, date_range.end))
    logins = LoginHistory.objects.filter(created_at__date__range=(date_range.start, date_range.end))
    backups = BackupJob.objects.filter(created_at__date__range=(date_range.start, date_range.end))
    if campus_id:
        events = events.filter(Q(campus_id=campus_id) | Q(campus__isnull=True))
    action_rows = [[item["action"], item["count"]] for item in events.values("action").annotate(count=Count("id")).order_by("-count")[:30]]
    user_rows = [[item["user__username"] or "Unknown", item["count"]] for item in events.values("user__username").annotate(count=Count("id")).order_by("-count")[:30]]
    login_rows = [[item["status"], item["count"]] for item in logins.values("status").annotate(count=Count("id"))]
    return AdvancedReport(
        title="Tenant Usage Report",
        description="See how actively this school tenant is being used through users, logins, exports, backups and audit events.",
        icon="ph-pulse",
        cards=[
            {"label": "Active users", "value": users.count(), "hint": "Enabled accounts"},
            {"label": "Activity events", "value": events.count(), "hint": "Recorded in selected period"},
            {"label": "Logins", "value": logins.count(), "hint": "Login attempts"},
            {"label": "Backups", "value": backups.count(), "hint": "Backup jobs"},
        ],
        tables=[
            {"title": "Activity by action", "headers": ["Action", "Count"], "rows": action_rows},
            {"title": "Most active users", "headers": ["User", "Events"], "rows": user_rows},
            {"title": "Login status", "headers": ["Status", "Count"], "rows": login_rows},
        ],
    )


REPORT_BUILDERS = {
    "student-performance": student_performance_report,
    "fee-collection": fee_collection_report,
    "attendance": attendance_summary_report,
    "teacher-workload": teacher_workload_report,
    "admissions": admission_report,
    "debtors": debtor_report,
    "payroll": payroll_report,
    "tenant-usage": tenant_usage_report,
}
