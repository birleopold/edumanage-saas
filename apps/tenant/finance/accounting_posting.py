from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .accounting_setup import get_account, setup_default_chart_of_accounts
from .models import CashAccount, FeeAdjustment, Invoice, JournalEntry, JournalLine, Payment, PayrollRun, SchoolExpense


def _sum(values):
    total = Decimal("0")
    for value in values:
        total += value or Decimal("0")
    return total


def make_entry(*, entry_date=None, reference="", description="", source=JournalEntry.MANUAL, lines=None, created_by=None, **refs):
    lines = lines or []
    debit = _sum([line.get("debit", Decimal("0")) for line in lines])
    credit = _sum([line.get("credit", Decimal("0")) for line in lines])
    if debit <= 0 or debit != credit:
        raise ValueError("Journal entry must balance.")
    entry = JournalEntry.objects.create(entry_date=entry_date or timezone.localdate(), reference=reference, description=description, source=source, status=JournalEntry.POSTED, posted_at=timezone.now(), created_by=created_by, **refs)
    JournalLine.objects.bulk_create([JournalLine(entry=entry, account=line["account"], description=line.get("description", ""), debit=line.get("debit", Decimal("0")), credit=line.get("credit", Decimal("0"))) for line in lines])
    return entry


def default_cash_account(payment):
    setup_default_chart_of_accounts()
    if payment.method == Payment.BANK:
        return CashAccount.objects.filter(kind=CashAccount.BANK, is_active=True).first()
    if payment.method == Payment.MOBILE:
        return CashAccount.objects.filter(kind=CashAccount.MOBILE_MONEY, is_active=True).first()
    if payment.method == Payment.CARD:
        return CashAccount.objects.filter(kind=CashAccount.BANK, is_active=True).first()
    return CashAccount.objects.filter(kind=CashAccount.CASH, is_active=True).first()


@transaction.atomic
def post_invoice_to_ledger(invoice: Invoice, *, created_by=None):
    if JournalEntry.objects.filter(source_invoice=invoice, source=JournalEntry.INVOICE).exists():
        return None
    receivable = get_account("1100")
    income = get_account("4000")
    equity = get_account("3000")
    lines_total = invoice.subtotal_lines()
    opening = invoice.opening_balance or Decimal("0")
    total = lines_total + opening
    if total <= 0:
        return None
    lines = [{"account": receivable, "debit": total, "description": "Fees invoice"}]
    if lines_total > 0:
        lines.append({"account": income, "credit": lines_total, "description": "School fees income"})
    if opening > 0:
        lines.append({"account": equity, "credit": opening, "description": "Opening balance"})
    return make_entry(entry_date=invoice.created_at.date() if invoice.created_at else timezone.localdate(), reference=invoice.reference or f"INV-{invoice.pk}", description=f"Invoice #{invoice.pk}", source=JournalEntry.INVOICE, lines=lines, created_by=created_by, source_invoice=invoice)


@transaction.atomic
def refresh_invoice_ledger(invoice: Invoice, *, created_by=None):
    if getattr(invoice, "_ledger_refreshed_by_signal", False):
        delattr(invoice, "_ledger_refreshed_by_signal")
        return None
    JournalEntry.objects.filter(source_invoice=invoice, source=JournalEntry.INVOICE).delete()
    return post_invoice_to_ledger(invoice, created_by=created_by)


@transaction.atomic
def post_payment_to_ledger(payment: Payment, *, created_by=None):
    if getattr(payment, "_ledger_posted_by_signal", False):
        delattr(payment, "_ledger_posted_by_signal")
        return None
    if JournalEntry.objects.filter(source_payment=payment, source=JournalEntry.PAYMENT).exists():
        return None
    cash = default_cash_account(payment)
    if not cash:
        raise ValueError("No cash, bank, or mobile money account configured.")
    amount = payment.amount or Decimal("0")
    if amount <= 0:
        return None
    return make_entry(entry_date=payment.received_at or timezone.localdate(), reference=payment.reference or f"PAY-{payment.pk}", description=f"Payment #{payment.pk}", source=JournalEntry.PAYMENT, lines=[{"account": cash.ledger_account, "debit": amount, "description": "Payment received"}, {"account": get_account("1100"), "credit": amount, "description": "Reduce fee receivable"}], created_by=created_by, source_payment=payment)


@transaction.atomic
def post_fee_adjustment_to_ledger(adjustment: FeeAdjustment, *, created_by=None):
    if JournalEntry.objects.filter(source_adjustment=adjustment, source=JournalEntry.ADJUSTMENT).exists():
        return None
    receivable = get_account("1100")
    amount = adjustment.amount or Decimal("0")
    if amount <= 0:
        return None
    if adjustment.adjustment_type in FeeAdjustment.REDUCE_TYPES:
        target = adjustment.account or get_account("4050")
        lines = [{"account": target, "debit": amount, "description": adjustment.description}, {"account": receivable, "credit": amount, "description": "Reduce receivable"}]
    elif adjustment.adjustment_type == FeeAdjustment.TAX:
        target = adjustment.account or get_account("2100")
        lines = [{"account": receivable, "debit": amount, "description": adjustment.description}, {"account": target, "credit": amount, "description": "Tax payable"}]
    else:
        target = adjustment.account or get_account("4100")
        lines = [{"account": receivable, "debit": amount, "description": adjustment.description}, {"account": target, "credit": amount, "description": "Penalty income"}]
    adjustment.is_posted = True
    adjustment.save(update_fields=["is_posted"])
    return make_entry(reference=f"ADJ-{adjustment.pk}", description=f"Fee adjustment #{adjustment.pk}", source=JournalEntry.ADJUSTMENT, lines=lines, created_by=created_by, source_adjustment=adjustment)


@transaction.atomic
def post_expense_to_ledger(expense: SchoolExpense, *, created_by=None):
    if JournalEntry.objects.filter(source_expense=expense, source=JournalEntry.EXPENSE).exists():
        return None
    amount = expense.amount or Decimal("0")
    if amount <= 0:
        return None
    entry = make_entry(entry_date=expense.expense_date, reference=expense.reference or f"EXP-{expense.pk}", description=expense.description, source=JournalEntry.EXPENSE, lines=[{"account": expense.category.expense_account, "debit": amount, "description": expense.description}, {"account": expense.paid_from.ledger_account, "credit": amount, "description": f"Paid from {expense.paid_from}"}], created_by=created_by, source_expense=expense)
    expense.is_posted = True
    expense.save(update_fields=["is_posted"])
    return entry


@transaction.atomic
def post_payroll_to_ledger(payroll: PayrollRun, *, created_by=None):
    if JournalEntry.objects.filter(source_payroll=payroll, source=JournalEntry.PAYROLL).exists():
        return None
    if not payroll.paid_from:
        raise ValueError("Select paid-from account before posting payroll.")
    amount = payroll.total_net_pay()
    if amount <= 0:
        return None
    entry = make_entry(entry_date=payroll.payment_date or timezone.localdate(), reference=f"PAYROLL-{payroll.pk}", description=payroll.name, source=JournalEntry.PAYROLL, lines=[{"account": get_account("5000"), "debit": amount, "description": payroll.name}, {"account": payroll.paid_from.ledger_account, "credit": amount, "description": "Payroll paid"}], created_by=created_by, source_payroll=payroll)
    payroll.is_posted = True
    payroll.status = PayrollRun.PAID
    payroll.save(update_fields=["is_posted", "status"])
    return entry
