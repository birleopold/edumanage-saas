from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import admin_portal_required

from .accounting_posting import post_expense_to_ledger, post_invoice_to_ledger, post_payment_to_ledger, post_payroll_to_ledger
from .accounting_reports import balance_sheet, cash_flow, income_statement, trial_balance
from .accounting_setup import setup_default_chart_of_accounts
from .csv_tools import import_cash_rows
from .export_tools import balance_sheet_csv, balance_sheet_xlsx, cash_flow_csv, cash_flow_xlsx, income_statement_csv, income_statement_xlsx, trial_balance_csv, trial_balance_xlsx
from .forms import PayrollRunForm, ReportDateRangeForm, SchoolExpenseForm, StatementImportForm
from .models import Account, CashAccount, Invoice, JournalEntry, Payment, PayrollRun, SchoolExpense
from .pdf_reports import cash_flow_pdf, trial_balance_pdf


def _date_param(request, name):
    raw = request.GET.get(name)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _download(name, content, content_type="text/csv"):
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


def _xlsx_response(name, stream):
    return _download(name, stream.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@admin_portal_required
def accounting_dashboard(request):
    summary = {"accounts": Account.objects.count(), "cash_accounts": CashAccount.objects.count(), "journal_entries": JournalEntry.objects.count(), "unposted_expenses": SchoolExpense.objects.filter(is_posted=False).count(), "unposted_payrolls": PayrollRun.objects.filter(is_posted=False).count()}
    recent_entries = JournalEntry.objects.prefetch_related("lines").order_by("-entry_date", "-id")[:20]
    return render(request, "portals/admin/finance/accounting/dashboard.html", {"summary": summary, "recent_entries": recent_entries})


@admin_portal_required
def chart_of_accounts(request):
    if request.method == "POST":
        result = setup_default_chart_of_accounts()
        messages.success(request, f"Default chart ready. Created {result['created_count']} account(s).")
        return redirect("finance_books_chart")
    accounts = Account.objects.select_related("parent").order_by("code")
    return render(request, "portals/admin/finance/accounting/chart_of_accounts.html", {"accounts": accounts})


@admin_portal_required
def cash_accounts(request):
    items = CashAccount.objects.select_related("ledger_account").order_by("kind", "name")
    return render(request, "portals/admin/finance/accounting/money_accounts.html", {"items": items})


@admin_portal_required
def journal_entries(request):
    qs = JournalEntry.objects.prefetch_related("lines", "lines__account").order_by("-entry_date", "-id")
    page_obj = Paginator(qs, 50).get_page(request.GET.get("page") or 1)
    return render(request, "portals/admin/finance/accounting/journal_entries.html", {"entries": page_obj.object_list, "page_obj": page_obj})


@admin_portal_required
def expense_create(request):
    form = SchoolExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        post_expense_to_ledger(obj, created_by=request.user)
        messages.success(request, "Expense saved and posted.")
        return redirect("finance_books_home")
    return render(request, "portals/admin/finance/accounting/form.html", {"form": form, "title": "Record Expense"})


@admin_portal_required
def payroll_create(request):
    form = PayrollRunForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        messages.success(request, "Payroll run created. Add payroll items in Django admin or payroll item screen.")
        return redirect("finance_books_home")
    return render(request, "portals/admin/finance/accounting/form.html", {"form": form, "title": "Create Payroll Run"})


@admin_portal_required
def statement_import(request):
    form = StatementImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        count = import_cash_rows(form.cleaned_data["statement_file"], form.cleaned_data["cash_account"])
        messages.success(request, f"Imported {count} row(s).")
        return redirect("finance_books_home")
    return render(request, "portals/admin/finance/accounting/form.html", {"form": form, "title": "Import Statement CSV"})


@admin_portal_required
def post_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    entry = post_invoice_to_ledger(invoice, created_by=request.user)
    messages.success(request, f"Invoice posted to ledger: {entry}" if entry else "Invoice was already posted or has no amount.")
    return redirect("admin_invoices_detail", pk=invoice.pk)


@admin_portal_required
def post_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    entry = post_payment_to_ledger(payment, created_by=request.user)
    messages.success(request, f"Payment posted to ledger: {entry}" if entry else "Payment was already posted or has no amount.")
    return redirect("admin_invoices_detail", pk=payment.invoice.pk)


@admin_portal_required
def post_expense(request, pk):
    expense = get_object_or_404(SchoolExpense, pk=pk)
    entry = post_expense_to_ledger(expense, created_by=request.user)
    messages.success(request, f"Expense posted to ledger: {entry}" if entry else "Expense was already posted or has no amount.")
    return redirect("finance_books_home")


@admin_portal_required
def post_payroll(request, pk):
    payroll = get_object_or_404(PayrollRun, pk=pk)
    entry = post_payroll_to_ledger(payroll, created_by=request.user)
    messages.success(request, f"Payroll posted to ledger: {entry}" if entry else "Payroll was already posted or has no net pay.")
    return redirect("finance_books_home")


@admin_portal_required
def trial_balance_report(request):
    start = _date_param(request, "start")
    end = _date_param(request, "end")
    rows = trial_balance(start, end)
    fmt = request.GET.get("format")
    if fmt == "csv":
        return _download("trial_balance.csv", trial_balance_csv(rows))
    if fmt == "xlsx":
        return _xlsx_response("trial_balance.xlsx", trial_balance_xlsx(rows))
    if fmt == "pdf":
        return _download("trial_balance.pdf", trial_balance_pdf(rows).read(), "application/pdf")
    return render(request, "portals/admin/finance/accounting/trial_balance.html", {"rows": rows, "start": start, "end": end, "filter_form": ReportDateRangeForm(request.GET or None)})


@admin_portal_required
def income_statement_report(request):
    start = _date_param(request, "start")
    end = _date_param(request, "end")
    report = income_statement(start, end)
    fmt = request.GET.get("format")
    if fmt == "csv":
        return _download("income_statement.csv", income_statement_csv(report))
    if fmt == "xlsx":
        return _xlsx_response("income_statement.xlsx", income_statement_xlsx(report))
    return render(request, "portals/admin/finance/accounting/income_statement.html", {"report": report, "start": start, "end": end, "filter_form": ReportDateRangeForm(request.GET or None)})


@admin_portal_required
def balance_sheet_report(request):
    as_of = _date_param(request, "as_of") or timezone.localdate()
    report = balance_sheet(as_of)
    fmt = request.GET.get("format")
    if fmt == "csv":
        return _download("financial_position.csv", balance_sheet_csv(report))
    if fmt == "xlsx":
        return _xlsx_response("financial_position.xlsx", balance_sheet_xlsx(report))
    return render(request, "portals/admin/finance/accounting/position.html", {"report": report, "as_of": as_of, "filter_form": ReportDateRangeForm(request.GET or None)})


@admin_portal_required
def cash_flow_report(request):
    start = _date_param(request, "start")
    end = _date_param(request, "end")
    report = cash_flow(start, end)
    fmt = request.GET.get("format")
    if fmt == "csv":
        return _download("cash_flow.csv", cash_flow_csv(report))
    if fmt == "xlsx":
        return _xlsx_response("cash_flow.xlsx", cash_flow_xlsx(report))
    if fmt == "pdf":
        return _download("cash_flow.pdf", cash_flow_pdf(report).read(), "application/pdf")
    return render(request, "portals/admin/finance/accounting/cash_flow.html", {"report": report, "start": start, "end": end, "filter_form": ReportDateRangeForm(request.GET or None)})
