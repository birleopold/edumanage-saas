import csv

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from apps.tenant.portals.permissions import admin_portal_required

from .advanced_services import REPORT_BUILDERS
from .admin_views import _base_context


REPORT_CATALOG = [
    {
        "key": "student-performance",
        "title": "Student performance reports",
        "description": "Class averages, learner averages, grades and students needing support.",
        "icon": "ph-chart-line-up",
    },
    {
        "key": "fee-collection",
        "title": "Fee collection reports",
        "description": "Billed fees, payments, collection rate, balances and payment methods.",
        "icon": "ph-wallet",
    },
    {
        "key": "attendance",
        "title": "Attendance reports",
        "description": "Attendance rate, absent/late totals, class attendance and frequent flags.",
        "icon": "ph-calendar-check",
    },
    {
        "key": "teacher-workload",
        "title": "Teacher workload reports",
        "description": "Course assignments, students, attendance sessions, assessments and workload score.",
        "icon": "ph-chalkboard-teacher",
    },
    {
        "key": "admissions",
        "title": "Admission reports",
        "description": "Applicant funnel, lead status, source tracking and conversion rate.",
        "icon": "ph-user-plus",
    },
    {
        "key": "debtors",
        "title": "Debtor reports",
        "description": "Outstanding balances, overdue invoices and top debtors for follow-up.",
        "icon": "ph-warning-circle",
    },
    {
        "key": "payroll",
        "title": "Payroll reports",
        "description": "Gross pay, deductions, net pay, payslip status and approval tracking.",
        "icon": "ph-bank",
    },
    {
        "key": "tenant-usage",
        "title": "Tenant usage reports",
        "description": "Active users, logins, audit events, exports, backups and usage by action.",
        "icon": "ph-pulse",
    },
]


def _report_url(key, request, view_name):
    query = request.GET.urlencode()
    url = reverse(view_name, kwargs={"report_key": key})
    return f"{url}?{query}" if query else url


def _catalog_with_urls(request):
    rows = []
    for item in REPORT_CATALOG:
        row = item.copy()
        row["url"] = _report_url(row["key"], request, "admin_reports_advanced_detail")
        row["csv_url"] = _report_url(row["key"], request, "admin_reports_advanced_csv")
        rows.append(row)
    return rows


@admin_portal_required
def advanced_reports_home(request):
    ctx = _base_context(request)
    ctx["reports"] = _catalog_with_urls(request)
    return render(request, "portals/admin/reports/advanced_home.html", ctx)


@admin_portal_required
def advanced_report_detail(request, report_key):
    builder = REPORT_BUILDERS.get(report_key)
    if not builder:
        raise Http404("Report not found")
    ctx = _base_context(request)
    report = builder(ctx["selected_campus_id"], ctx["date_range"])
    ctx.update(
        {
            "report": report,
            "report_key": report_key,
            "reports": _catalog_with_urls(request),
            "csv_url": _report_url(report_key, request, "admin_reports_advanced_csv"),
        }
    )
    return render(request, "portals/admin/reports/advanced_detail.html", ctx)


@admin_portal_required
def advanced_report_csv(request, report_key):
    builder = REPORT_BUILDERS.get(report_key)
    if not builder:
        raise Http404("Report not found")
    ctx = _base_context(request)
    report = builder(ctx["selected_campus_id"], ctx["date_range"])
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{report_key}_{ctx["start"].isoformat()}_{ctx["end"].isoformat()}.csv"'
    writer = csv.writer(response)
    writer.writerow([report.title])
    writer.writerow([report.description])
    writer.writerow([])
    writer.writerow(["summary", "value", "note"])
    for card in report.cards:
        writer.writerow([card.get("label"), card.get("value"), card.get("hint")])
    for table in report.tables:
        writer.writerow([])
        writer.writerow([table["title"]])
        writer.writerow(table["headers"])
        for row in table["rows"]:
            writer.writerow(row)
    return response
