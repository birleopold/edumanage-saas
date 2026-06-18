from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.portals.permissions import admin_portal_required

from .accounting_posting import post_expense_to_ledger, post_invoice_to_ledger, post_payment_to_ledger, post_payroll_to_ledger
from .accounting_reports import balance_sheet, cash_flow, income_statement, trial_balance
from .accounting_setup import setup_default_chart_of_accounts
from .models import Account, BankReconciliation, CashAccount, Invoice, JournalEntry, Payment, PayrollRun, SchoolExpense


def _date_param(request, name):
    raw = request.GET.get(name)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


@admin_portal_required
def accounting_dashboard(request):
    summary = {
        "accounts": Account.objects.count(),
        "cash_accounts": CashAccount.objects.count(),
        "journal_entries": JournalEntry.objects.count(),
        "unposted_expenses": SchoolExpense.objects.filter(is_posted=False).count(),
        "unposted_payrolls": PayrollRun.objects.filter(is_posted=False).count(),
    }
    recent_entries = JournalEntry.objects.prefetch_related("lines").order_by("-entry_date", "-id")[:20]
    return render(request, "portals/admin/finance/accounting/dashboard.html", {"summary": summary, "recent_entries": recent_entries})


@admin_portal_required
def chart_of_accounts(request):
    if request.method == "POST":
        result = setup_default_chart_of_accounts()
        messages.success(request, f"Default chart ready. Created {result['created_count']} account(s).")
        return redirect("admin_finance_chart_of_accounts")
    accounts = Account.objects.select_related("parent").order_by("code")
    return render(request, "portals/admin/finance/accounting/chart_of_accounts.html", {"accounts": accounts})


@admin_portal_required
def cash_accounts(request):
    items = CashAccount.objects.select_related("ledger_account").order_by("kind", "name")
    return render(request, "portals/admin/finance/accounting/cash_accounts.html", {"items": items})


@admin_portal_required
def journal_entries(request):
    qs = JournalEntry.objects.prefetch_related("lines", "lines__account").order_by("-entry_date", "-id")
    page_obj = Paginator(qs, 50).get_page(request.GET.get("page") or 1)
    return render(request, "portals/admin/finance/accounting/journal_entries.html", {"entries": page_obj.object_list, "page_obj": page_obj})


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
    return redirect("admin_finance_accounting_dashboard")


@admin_portal_required
def post_payroll(request, pk):
    payroll = get_object_or_404(PayrollRun, pk=pk)
    entry = post_payroll_to_ledger(payroll, created_by=request.user)
    messages.success(request, f"Payroll posted to ledger: {entry}" if entry else "Payroll was already posted or has no net pay.")
    return redirect("admin_finance_accounting_dashboard")


@admin_portal_required
def trial_balance_report(request):
    start = _date_param(request, "start")
    end = _date_param(request, "end")
    return render(request, "portals/admin/finance/accounting/trial_balance.html", {"rows": trial_balance(start, end), "start": start, "end": end})


@admin_portal_required
def income_statement_report(request):
    start = _date_param(request, "start")
    end = _date_param(request, "end")
    return render(request, "portals/admin/finance/accounting/income_statement.html", {"report": income_statement(start, end), "start": start, "end": end})


@admin_portal_required
def balance_sheet_report(request):
    as_of = _date_param(request, "as_of") or timezone.localdate()
    return render(request, "portals/admin/finance/accounting/balance_sheet.html", {"report": balance_sheet(as_of), "as_of": as_of})


@admin_portal_required
def cash_flow_report(request):
    start = _date_param(request, "start")
    end = _date_param(request, "end")
    return render(request, "portals/admin/finance/accounting/cash_flow.html", {"report": cash_flow(start, end), "start": start, "end": end})
