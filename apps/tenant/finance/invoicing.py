from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear
from apps.tenant.students.models import StudentProfile

from .models import FeeItem, Invoice, InvoiceLine


@dataclass(frozen=True)
class InvoiceAmounts:
    subtotal_lines: Decimal
    opening_balance: Decimal
    total_amount: Decimal
    total_paid: Decimal
    balance: Decimal
    display_status: str
    is_overdue: bool


@dataclass(frozen=True)
class CollectionSummary:
    invoice_count: int
    total_billed: Decimal
    total_paid: Decimal
    total_balance: Decimal
    overdue_count: int
    paid_count: int
    partial_count: int
    unpaid_count: int


def invoice_amounts(invoice: Invoice, *, today: date | None = None) -> InvoiceAmounts:
    today = today or timezone.localdate()
    subtotal_lines = invoice.subtotal_lines()
    opening_balance = invoice.opening_balance or Decimal("0")
    total_amount = opening_balance + subtotal_lines
    total_paid = invoice.total_paid()
    balance = total_amount - total_paid
    is_overdue = bool(invoice.due_date and invoice.due_date < today and balance > 0)

    if balance <= 0 and total_amount > 0:
        display_status = "PAID"
    elif total_paid > 0 and balance > 0:
        display_status = "PARTIAL"
    elif is_overdue:
        display_status = "OVERDUE"
    elif invoice.status == Invoice.CLOSED:
        display_status = "CLOSED"
    else:
        display_status = "UNPAID"

    return InvoiceAmounts(
        subtotal_lines=subtotal_lines,
        opening_balance=opening_balance,
        total_amount=total_amount,
        total_paid=total_paid,
        balance=balance,
        display_status=display_status,
        is_overdue=is_overdue,
    )


def attach_invoice_amounts(invoices: Iterable[Invoice]) -> list[Invoice]:
    today = timezone.localdate()
    result = []
    for invoice in invoices:
        amounts = invoice_amounts(invoice, today=today)
        invoice.subtotal_lines_amount = amounts.subtotal_lines
        invoice.total_amount_value = amounts.total_amount
        invoice.total_paid_value = amounts.total_paid
        invoice.balance_value = amounts.balance
        invoice.display_status = amounts.display_status
        invoice.is_overdue = amounts.is_overdue
        result.append(invoice)
    return result


def collection_summary(invoices: Iterable[Invoice]) -> CollectionSummary:
    total_billed = Decimal("0")
    total_paid = Decimal("0")
    total_balance = Decimal("0")
    overdue_count = 0
    paid_count = 0
    partial_count = 0
    unpaid_count = 0
    invoice_count = 0

    for invoice in invoices:
        invoice_count += 1
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

    return CollectionSummary(
        invoice_count=invoice_count,
        total_billed=total_billed,
        total_paid=total_paid,
        total_balance=total_balance,
        overdue_count=overdue_count,
        paid_count=paid_count,
        partial_count=partial_count,
        unpaid_count=unpaid_count,
    )


def build_invoice_reference(student: StudentProfile, year: AcademicYear | None, term: AcademicTerm | None, prefix: str = "INV") -> str:
    prefix = (prefix or "INV").strip().upper().replace(" ", "-")[:16]
    year_part = (getattr(year, "name", "") or timezone.localdate().strftime("%Y")).replace(" ", "")[:12]
    term_part = (getattr(term, "name", "") or "TERM").replace(" ", "")[:12]
    student_part = (student.student_id or f"ST{student.pk}").replace(" ", "").replace("/", "-")[:20]
    base = f"{prefix}-{year_part}-{term_part}-{student_part}"
    reference = base
    counter = 2
    while Invoice.objects.filter(reference=reference).exists():
        reference = f"{base}-{counter}"
        counter += 1
    return reference[:64]


def invoice_exists_for_period(student: StudentProfile, year: AcademicYear | None, term: AcademicTerm | None) -> bool:
    return Invoice.objects.filter(student=student, academic_year=year, academic_term=term).exists()


@transaction.atomic
def create_invoice_from_fee_items(
    *,
    student: StudentProfile,
    academic_year: AcademicYear | None,
    academic_term: AcademicTerm | None,
    fee_items: Iterable[FeeItem],
    due_date: date | None = None,
    opening_balance: Decimal | int | str | None = None,
    reference_prefix: str = "INV",
    skip_existing: bool = True,
) -> tuple[Invoice | None, str]:
    if skip_existing and invoice_exists_for_period(student, academic_year, academic_term):
        return None, "skipped_existing"

    items = list(fee_items)
    if not items:
        return None, "no_fee_items"

    invoice = Invoice.objects.create(
        student=student,
        academic_year=academic_year,
        academic_term=academic_term,
        reference=build_invoice_reference(student, academic_year, academic_term, reference_prefix),
        due_date=due_date,
        opening_balance=Decimal(str(opening_balance or "0")),
        status=Invoice.ACTIVE,
    )
    InvoiceLine.objects.bulk_create(
        [
            InvoiceLine(
                invoice=invoice,
                fee_item=item,
                description=item.name,
                quantity=Decimal("1"),
                unit_amount=item.amount,
            )
            for item in items
        ]
    )
    return invoice, "created"


@transaction.atomic
def bulk_create_invoices(
    *,
    students: QuerySet | Iterable[StudentProfile],
    academic_year: AcademicYear | None,
    academic_term: AcademicTerm | None,
    fee_items: Iterable[FeeItem],
    due_date: date | None = None,
    opening_balance: Decimal | int | str | None = None,
    reference_prefix: str = "INV",
    skip_existing: bool = True,
) -> dict:
    created = []
    skipped_existing = []
    failed = []
    items = list(fee_items)

    for student in students:
        invoice, status = create_invoice_from_fee_items(
            student=student,
            academic_year=academic_year,
            academic_term=academic_term,
            fee_items=items,
            due_date=due_date,
            opening_balance=opening_balance,
            reference_prefix=reference_prefix,
            skip_existing=skip_existing,
        )
        if status == "created" and invoice:
            created.append(invoice)
        elif status == "skipped_existing":
            skipped_existing.append(student)
        else:
            failed.append({"student": student, "reason": status})

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "created_count": len(created),
        "skipped_existing_count": len(skipped_existing),
        "failed_count": len(failed),
    }
