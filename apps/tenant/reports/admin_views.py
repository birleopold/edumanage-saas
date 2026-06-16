import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.contrib import messages
from django.db.models import Avg, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.academics.models import Enrollment
from apps.tenant.exams.models import Exam, ExamPaper, ExamScore
from apps.tenant.finance.models import Invoice, InvoiceLine, Payment
from apps.tenant.parents.models import ParentProfile
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import ReportRun
from .scheduler import execute_overview_csv_run
from .services import (
    DateRange,
    academic_performance_report,
    attendance_report,
    finance_report,
    school_dashboard_summary,
)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _date_range_from_request(request) -> Tuple[date, date]:
    end = _parse_date(request.GET.get("end")) or timezone.localdate()
    start = _parse_date(request.GET.get("start")) or (end - timedelta(days=30))
    if start > end:
        start, end = end, start
    return start, end


def _range_obj(start: date, end: date) -> DateRange:
    return DateRange(start=start, end=end)


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _selected_campus_id(request) -> Optional[int]:
    current = get_current_campus(request)
    if "campus" in request.GET:
        raw = request.GET.get("campus")
        if raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return current.id if current else None


def _base_context(request):
    start, end = _date_range_from_request(request)
    campus_id = _selected_campus_id(request)
    return {
        "start": start,
        "end": end,
        "date_range": _range_obj(start, end),
        "campuses": _campus_queryset(),
        "selected_campus_id": campus_id,
    }


def _compute_metrics(start: date, end: date, campus_id: Optional[int]) -> list[tuple[str, object]]:
    date_range = (start, end)

    metrics: list[tuple[str, object]] = []

    metrics.append(("Date range start", start.isoformat()))
    metrics.append(("Date range end", end.isoformat()))

    if campus_id:
        campus_name = Campus.objects.filter(id=campus_id).values_list("name", flat=True).first()
        metrics.append(("Campus", campus_name or campus_id))
    else:
        metrics.append(("Campus", "All"))

    students_qs = StudentProfile.objects.all()
    teachers_qs = TeacherProfile.objects.all()
    enrollments_qs = Enrollment.objects.all()

    if campus_id:
        students_qs = students_qs.filter(campus_id=campus_id)
        teachers_qs = teachers_qs.filter(campus_id=campus_id)
        enrollments_qs = enrollments_qs.filter(campus_id=campus_id)

    metrics.append(("Students (total)", students_qs.count()))
    metrics.append(
        (
            "Students (created in range)",
            students_qs.filter(created_at__date__range=date_range).count(),
        )
    )

    metrics.append(("Teachers (total)", teachers_qs.count()))

    if campus_id:
        parents_count = (
            ParentProfile.objects.filter(parentstudentlink__student__campus_id=campus_id)
            .distinct()
            .count()
        )
    else:
        parents_count = ParentProfile.objects.count()

    metrics.append(("Parents (total)", parents_count))

    metrics.append(("Enrollments (active)", enrollments_qs.filter(status=Enrollment.ACTIVE).count()))
    metrics.append(("Enrollments (dropped)", enrollments_qs.filter(status=Enrollment.DROPPED).count()))
    metrics.append(
        (
            "Enrollments (created in range)",
            enrollments_qs.filter(created_at__date__range=date_range).count(),
        )
    )

    sessions_qs = AttendanceSession.objects.filter(date__range=date_range)
    if campus_id:
        sessions_qs = sessions_qs.filter(offering__campus_id=campus_id)
    metrics.append(("Attendance sessions (in range)", sessions_qs.count()))

    attendance_entries_qs = AttendanceEntry.objects.filter(session__date__range=date_range)
    if campus_id:
        attendance_entries_qs = attendance_entries_qs.filter(session__offering__campus_id=campus_id)
    metrics.append(("Attendance entries (in range)", attendance_entries_qs.count()))
    metrics.append(("Attendance present (in range)", attendance_entries_qs.filter(status=AttendanceEntry.PRESENT).count()))
    metrics.append(("Attendance absent (in range)", attendance_entries_qs.filter(status=AttendanceEntry.ABSENT).count()))
    metrics.append(("Attendance late (in range)", attendance_entries_qs.filter(status=AttendanceEntry.LATE).count()))
    metrics.append(("Attendance excused (in range)", attendance_entries_qs.filter(status=AttendanceEntry.EXCUSED).count()))

    invoices_in_range = Invoice.objects.filter(created_at__date__range=date_range)
    if campus_id:
        invoices_in_range = invoices_in_range.filter(student__campus_id=campus_id)
    metrics.append(("Invoices (created in range)", invoices_in_range.count()))

    line_total_expr = ExpressionWrapper(
        F("quantity") * F("unit_amount"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    invoiced_amount_range = (
        InvoiceLine.objects.filter(invoice__in=invoices_in_range).aggregate(total=Sum(line_total_expr)).get("total")
        or 0
    )

    paid_amount_for_invoices_range = (
        Payment.objects.filter(invoice__in=invoices_in_range).aggregate(total=Sum("amount")).get("total")
        or 0
    )

    metrics.append(("Invoiced amount (in range)", invoiced_amount_range))
    metrics.append(("Paid amount (for invoices in range)", paid_amount_for_invoices_range))
    metrics.append(("Outstanding (for invoices in range)", invoiced_amount_range - paid_amount_for_invoices_range))

    metrics.append(("Exams (total)", Exam.objects.count()))
    papers_total = ExamPaper.objects.all()
    if campus_id:
        papers_total = papers_total.filter(offering__campus_id=campus_id)
    metrics.append(("Exam papers (total)", papers_total.count()))

    papers_in_range = ExamPaper.objects.filter(created_at__date__range=date_range)
    if campus_id:
        papers_in_range = papers_in_range.filter(offering__campus_id=campus_id)
    metrics.append(("Exam papers (created in range)", papers_in_range.count()))
    metrics.append(("Exam papers (published in range)", papers_in_range.filter(is_published=True).count()))

    scores_in_range = ExamScore.objects.filter(paper__in=papers_in_range)
    metrics.append(("Exam scores (for papers created in range)", scores_in_range.count()))
    metrics.append(("Exam average score (for papers created in range)", scores_in_range.aggregate(avg=Avg("score")).get("avg")))

    return metrics


@admin_portal_required
def overview(request):
    ctx = _base_context(request)
    start = ctx["start"]
    end = ctx["end"]
    campus_id = ctx["selected_campus_id"]
    date_range = ctx["date_range"]
    metrics = _compute_metrics(start, end, campus_id)
    dashboard = school_dashboard_summary(campus_id, date_range)

    ctx.update({"metrics": metrics, "dashboard": dashboard})
    return render(request, "portals/admin/reports/overview.html", ctx)


@admin_portal_required
def finance_report_view(request):
    ctx = _base_context(request)
    ctx["report"] = finance_report(ctx["selected_campus_id"], ctx["date_range"])
    return render(request, "portals/admin/reports/finance.html", ctx)


@admin_portal_required
def attendance_report_view(request):
    ctx = _base_context(request)
    ctx["report"] = attendance_report(ctx["selected_campus_id"], ctx["date_range"])
    return render(request, "portals/admin/reports/attendance.html", ctx)


@admin_portal_required
def academic_performance_report_view(request):
    ctx = _base_context(request)
    ctx["report"] = academic_performance_report(ctx["selected_campus_id"], ctx["date_range"])
    return render(request, "portals/admin/reports/academic_performance.html", ctx)


@admin_portal_required
def overview_csv(request):
    start, end = _date_range_from_request(request)
    campus_id = _selected_campus_id(request)
    metrics = _compute_metrics(start, end, campus_id)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="reports_overview_{start.isoformat()}_{end.isoformat()}.csv"'

    writer = csv.writer(response)
    writer.writerow(["metric", "value"])
    for name, value in metrics:
        writer.writerow([name, value])

    return response


@admin_portal_required
def finance_csv(request):
    start, end = _date_range_from_request(request)
    report = finance_report(_selected_campus_id(request), _range_obj(start, end))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="finance_report_{start.isoformat()}_{end.isoformat()}.csv"'
    writer = csv.writer(response)
    writer.writerow(["section", "item", "count", "amount"])
    writer.writerow(["summary", "invoices", report.invoice_count, ""])
    writer.writerow(["summary", "total_billed", "", report.total_billed])
    writer.writerow(["summary", "total_paid", "", report.total_paid])
    writer.writerow(["summary", "total_balance", "", report.total_balance])
    for row in report.by_method:
        writer.writerow(["payment_method", row["method"], row["count"], row["amount"]])
    for row in report.top_debtors:
        writer.writerow(["top_debtor", row["student"], row["invoice"].reference or row["invoice"].pk, row["balance"]])
    return response


@admin_portal_required
def attendance_csv(request):
    start, end = _date_range_from_request(request)
    report = attendance_report(_selected_campus_id(request), _range_obj(start, end))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="attendance_report_{start.isoformat()}_{end.isoformat()}.csv"'
    writer = csv.writer(response)
    writer.writerow(["offering", "entries", "present", "absent", "late", "excused", "attendance_rate"])
    for row in report.by_offering:
        writer.writerow([row["offering"], row["entries"], row["present"], row["absent"], row["late"], row["excused"], row["rate"]])
    writer.writerow([])
    writer.writerow(["frequent_absentee", "absent", "late", "total_flags"])
    for row in report.frequent_absentees:
        writer.writerow([row["student"], row["absent"], row["late"], row["total_flags"]])
    return response


@admin_portal_required
def academic_performance_csv(request):
    start, end = _date_range_from_request(request)
    report = academic_performance_report(_selected_campus_id(request), _range_obj(start, end))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="academic_performance_{start.isoformat()}_{end.isoformat()}.csv"'
    writer = csv.writer(response)
    writer.writerow(["offering", "scores", "average_percentage", "grade", "remark"])
    for row in report.by_offering:
        writer.writerow([row["offering"], row["count"], row["average"], row["grade"], row["remark"]])
    writer.writerow([])
    writer.writerow(["student", "scores", "average_percentage", "grade", "remark"])
    for row in report.student_averages:
        writer.writerow([row["student"], row["count"], row["average"], row["grade"], row["remark"]])
    return response


@admin_portal_required
def scheduled_reports(request):
    runs = ReportRun.objects.order_by("-created_at")[:100]
    return render(
        request,
        "portals/admin/reports/scheduled.html",
        {"runs": runs},
    )


@admin_portal_required
def scheduled_report_run_now(request):
    if request.method != "POST":
        return redirect("admin_reports_scheduled")
    start, end = _date_range_from_request(request)
    campus_id = _selected_campus_id(request)
    run = execute_overview_csv_run(triggered_by=request.user, start=start, end=end, campus_id=campus_id)
    if run.status == ReportRun.STATUS_SUCCESS:
        messages.success(request, "Overview CSV generated. Download from the list below.")
    else:
        messages.error(request, run.detail or "Report generation failed.")
    return redirect("admin_reports_scheduled")


@admin_portal_required
def report_run_download(request, pk: int):
    run = get_object_or_404(ReportRun, pk=pk)
    if run.status != ReportRun.STATUS_SUCCESS or not run.file_path:
        raise Http404("File not available.")
    if not run.file_path.startswith("generated_reports/"):
        raise Http404("Invalid path.")
    path = Path(settings.MEDIA_ROOT) / run.file_path
    if not path.is_file():
        raise Http404("File missing on disk.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
