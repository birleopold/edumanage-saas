import csv
import json
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant.portals.permissions import admin_portal_required

from .models import AuditEvent, BackupJob
from .services import log_audit


EXPORT_DEFINITIONS = {
    "students": {
        "title": "Export students",
        "description": "Download active and inactive learner records with class/stream, campus and learner identifiers.",
        "icon": "ph-student",
        "filename": "students.csv",
    },
    "fee-balances": {
        "title": "Export fee balances",
        "description": "Download invoices, totals paid, balances, academic year and term for finance follow-up.",
        "icon": "ph-wallet",
        "filename": "fee_balances.csv",
    },
    "marks": {
        "title": "Export marks",
        "description": "Download assessment marks, maximum score, teacher grading details and publication status.",
        "icon": "ph-exam",
        "filename": "marks.csv",
    },
    "attendance": {
        "title": "Export attendance",
        "description": "Download attendance sessions, learner status, class/course context and teacher who took attendance.",
        "icon": "ph-calendar-check",
        "filename": "attendance.csv",
    },
    "payroll": {
        "title": "Export payroll",
        "description": "Download payslip summaries, gross pay, deductions, net salary and approval/payment status.",
        "icon": "ph-bank",
        "filename": "payroll.csv",
    },
}


def _stringify(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_stringify(row.get(header, "")) for header in headers])
    return response


def _student_rows():
    from apps.tenant.students.models import StudentProfile

    headers = ["student_id", "learner_id", "first_name", "last_name", "email", "campus", "stream", "district", "subcounty", "parish", "is_active", "created_at"]
    rows = []
    for student in StudentProfile.objects.select_related("campus", "stream").order_by("last_name", "first_name"):
        rows.append(
            {
                "student_id": student.student_id,
                "learner_id": student.learner_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
                "campus": student.campus,
                "stream": student.stream,
                "district": student.district,
                "subcounty": student.subcounty,
                "parish": student.parish,
                "is_active": student.is_active,
                "created_at": student.created_at,
            }
        )
    return headers, rows


def _fee_balance_rows():
    from apps.tenant.finance.models import Invoice

    headers = ["invoice_id", "reference", "student", "student_id", "academic_year", "academic_term", "due_date", "status", "total_amount", "total_paid", "balance", "created_at"]
    rows = []
    for invoice in Invoice.objects.select_related("student", "academic_year", "academic_term").prefetch_related("lines", "payments").order_by("-created_at"):
        rows.append(
            {
                "invoice_id": invoice.id,
                "reference": invoice.reference,
                "student": invoice.student.get_full_name() if invoice.student else "",
                "student_id": getattr(invoice.student, "student_id", ""),
                "academic_year": invoice.academic_year,
                "academic_term": invoice.academic_term,
                "due_date": invoice.due_date,
                "status": invoice.get_status_display(),
                "total_amount": invoice.total_amount(),
                "total_paid": invoice.total_paid(),
                "balance": invoice.balance(),
                "created_at": invoice.created_at,
            }
        )
    return headers, rows


def _marks_rows():
    from apps.tenant.assessments.models import AssessmentScore

    headers = ["assessment", "student", "student_id", "score", "max_score", "note", "graded_by", "graded_at", "is_published"]
    rows = []
    for score in AssessmentScore.objects.select_related("assessment", "student", "graded_by").order_by("assessment__name", "student__last_name", "student__first_name"):
        rows.append(
            {
                "assessment": score.assessment,
                "student": score.student.get_full_name() if score.student else "",
                "student_id": getattr(score.student, "student_id", ""),
                "score": score.score,
                "max_score": score.assessment.max_score if score.assessment else "",
                "note": score.note,
                "graded_by": score.graded_by,
                "graded_at": score.graded_at,
                "is_published": score.assessment.is_published if score.assessment else "",
            }
        )
    return headers, rows


def _attendance_rows():
    from apps.tenant.attendance.models import AttendanceEntry

    headers = ["date", "offering", "student", "student_id", "status", "note", "taken_by"]
    rows = []
    for entry in AttendanceEntry.objects.select_related("session", "session__offering", "session__taken_by", "student").order_by("-session__date", "student__last_name", "student__first_name"):
        rows.append(
            {
                "date": entry.session.date if entry.session else "",
                "offering": entry.session.offering if entry.session else "",
                "student": entry.student.get_full_name() if entry.student else "",
                "student_id": getattr(entry.student, "student_id", ""),
                "status": entry.get_status_display(),
                "note": entry.note,
                "taken_by": entry.session.taken_by if entry.session else "",
            }
        )
    return headers, rows


def _payroll_rows():
    from apps.tenant.hr.models import Payslip

    headers = ["payslip_id", "staff", "staff_id", "year", "month", "base_salary", "gross_salary", "allowances", "deductions", "net_salary", "status", "generated_by", "generated_at", "approved_by", "approved_at", "paid_at"]
    rows = []
    for payslip in Payslip.objects.select_related("staff", "generated_by", "approved_by").order_by("-period_year", "-period_month", "staff__last_name"):
        rows.append(
            {
                "payslip_id": payslip.id,
                "staff": payslip.staff.get_full_name() if payslip.staff else "",
                "staff_id": getattr(payslip.staff, "staff_id", ""),
                "year": payslip.period_year,
                "month": payslip.period_month,
                "base_salary": payslip.base_salary,
                "gross_salary": payslip.gross_salary,
                "allowances": payslip.total_allowances,
                "deductions": payslip.total_deductions,
                "net_salary": payslip.net_salary,
                "status": payslip.get_status_display(),
                "generated_by": payslip.generated_by,
                "generated_at": payslip.generated_at,
                "approved_by": payslip.approved_by,
                "approved_at": payslip.approved_at,
                "paid_at": payslip.paid_at,
            }
        )
    return headers, rows


EXPORT_BUILDERS = {
    "students": _student_rows,
    "fee-balances": _fee_balance_rows,
    "marks": _marks_rows,
    "attendance": _attendance_rows,
    "payroll": _payroll_rows,
}


@admin_portal_required
def export_center(request):
    return render(
        request,
        "portals/audit/export_center.html",
        {
            "exports": EXPORT_DEFINITIONS,
            "backups": BackupJob.objects.all()[:10],
        },
    )


@admin_portal_required
def download_export(request, export_key):
    if export_key not in EXPORT_BUILDERS:
        return redirect("audit_export_center")
    headers, rows = EXPORT_BUILDERS[export_key]()
    definition = EXPORT_DEFINITIONS[export_key]
    log_audit(
        request,
        action=AuditEvent.EXPORT,
        object_label=definition["title"],
        metadata={"export_key": export_key, "row_count": len(rows), "filename": definition["filename"]},
    )
    return _csv_response(definition["filename"], headers, rows)


def _backup_payload():
    payload = {
        "generated_at": timezone.now().isoformat(),
        "datasets": {},
    }
    for key, builder in EXPORT_BUILDERS.items():
        headers, rows = builder()
        payload["datasets"][key] = {
            "headers": headers,
            "rows": [{header: _stringify(row.get(header, "")) for header in headers} for row in rows],
            "row_count": len(rows),
        }
    return payload


@admin_portal_required
@require_POST
def request_backup(request):
    notes = request.POST.get("notes") or "Manual school data backup requested"
    payload = _backup_payload()
    job = BackupJob.objects.create(
        requested_by=request.user,
        status=BackupJob.SUCCESS,
        notes=f"{notes}. Included datasets: {', '.join(payload['datasets'].keys())}",
        file_path=f"school_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json",
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )
    log_audit(
        request,
        action=AuditEvent.EXPORT,
        object_label="School data backup",
        metadata={"backup_job_id": job.id, "datasets": list(payload["datasets"].keys())},
    )
    response = HttpResponse(json.dumps(payload, indent=2), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{job.file_path}"'
    return response
