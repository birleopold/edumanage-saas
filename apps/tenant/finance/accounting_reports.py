from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Account, BankReconciliation, CashAccount, JournalEntry, JournalLine


def account_activity(account, start_date=None, end_date=None):
    qs = JournalLine.objects.filter(account=account, entry__status=JournalEntry.POSTED)
    if start_date:
        qs = qs.filter(entry__entry_date__gte=start_date)
    if end_date:
        qs = qs.filter(entry__entry_date__lte=end_date)
    debit = qs.aggregate(total=Sum("debit"))["total"] or Decimal("0")
    credit = qs.aggregate(total=Sum("credit"))["total"] or Decimal("0")
    return debit, credit


def account_balance(account, start_date=None, end_date=None):
    debit, credit = account_activity(account, start_date, end_date)
    if account.account_type in [Account.ASSET, Account.EXPENSE]:
        return debit - credit
    return credit - debit


def trial_balance(start_date=None, end_date=None):
    rows = []
    for account in Account.objects.filter(is_active=True).order_by("code"):
        debit, credit = account_activity(account, start_date, end_date)
        rows.append({"account": account, "debit_total": debit, "credit_total": credit, "balance": account_balance(account, start_date, end_date)})
    return rows


def income_statement(start_date=None, end_date=None):
    income_rows = []
    expense_rows = []
    total_income = Decimal("0")
    total_expenses = Decimal("0")
    for account in Account.objects.filter(is_active=True, account_type__in=[Account.INCOME, Account.EXPENSE]).order_by("code"):
        amount = account_balance(account, start_date, end_date)
        row = {"account": account, "amount": amount}
        if account.account_type == Account.INCOME:
            income_rows.append(row)
            total_income += amount
        else:
            expense_rows.append(row)
            total_expenses += amount
    return {"income_rows": income_rows, "expense_rows": expense_rows, "total_income": total_income, "total_expenses": total_expenses, "net_income": total_income - total_expenses}


def balance_sheet(as_of=None):
    as_of = as_of or timezone.localdate()
    rows = {Account.ASSET: [], Account.LIABILITY: [], Account.EQUITY: []}
    totals = {Account.ASSET: Decimal("0"), Account.LIABILITY: Decimal("0"), Account.EQUITY: Decimal("0")}
    for account in Account.objects.filter(is_active=True, account_type__in=rows.keys()).order_by("code"):
        amount = account_balance(account, end_date=as_of)
        rows[account.account_type].append({"account": account, "amount": amount})
        totals[account.account_type] += amount
    return {"rows": rows, "totals": totals, "as_of": as_of}


def cash_flow(start_date=None, end_date=None):
    rows = []
    total_in = Decimal("0")
    total_out = Decimal("0")
    for cash in CashAccount.objects.filter(is_active=True).select_related("ledger_account"):
        debit, credit = account_activity(cash.ledger_account, start_date, end_date)
        rows.append({"cash_account": cash, "cash_in": debit, "cash_out": credit, "net": debit - credit})
        total_in += debit
        total_out += credit
    return {"rows": rows, "total_in": total_in, "total_out": total_out, "net_cash_flow": total_in - total_out}


def refresh_reconciliation(reconciliation: BankReconciliation):
    reconciliation.system_balance = account_balance(reconciliation.cash_account.ledger_account, end_date=reconciliation.statement_date)
    reconciliation.save()
    return reconciliation
