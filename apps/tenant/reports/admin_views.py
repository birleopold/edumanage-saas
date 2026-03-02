import csv
from datetime import date, timedelta
from typing import Optional, Tuple

from django.db.models import Avg, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.academics.models import Enrollment
from apps.tenant.exams.models import Exam, ExamPaper, ExamScore
from apps.tenant.finance.models import Invoice, InvoiceLine, Payment
from apps.tenant.parents.models import ParentProfile
from apps.tenant.parents.models import ParentStudentLink
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role


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
    metrics.append(
        (
            "Attendance present (in range)",
            attendance_entries_qs.filter(status=AttendanceEntry.PRESENT).count(),
        )
    )
    metrics.append(
        (
            "Attendance absent (in range)",
            attendance_entries_qs.filter(status=AttendanceEntry.ABSENT).count(),
        )
    )
    metrics.append(
        (
            "Attendance late (in range)",
            attendance_entries_qs.filter(status=AttendanceEntry.LATE).count(),
        )
    )
    metrics.append(
        (
            "Attendance excused (in range)",
            attendance_entries_qs.filter(status=AttendanceEntry.EXCUSED).count(),
        )
    )

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


@role_required(Role.ADMIN)
def overview(request):
    start, end = _date_range_from_request(request)
    campuses = _campus_queryset()
    campus_id = _selected_campus_id(request)
    metrics = _compute_metrics(start, end, campus_id)

    return render(
        request,
        "portals/admin/reports/overview.html",
        {"start": start, "end": end, "metrics": metrics, "campuses": campuses, "selected_campus_id": campus_id},
    )


@role_required(Role.ADMIN)
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
