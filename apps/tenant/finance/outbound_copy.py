"""
Placeholder rendering and DB-backed message templates for SMS/WhatsApp copy.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional

from .models import CommunicationTemplate


def apply_communication_placeholders(body: str, context: dict[str, Any]) -> str:
    """Replace {{key}} tokens; missing keys become empty strings."""

    if not body:
        return ""

    def repl(match: re.Match) -> str:
        key = (match.group(1) or "").strip()
        val = context.get(key)
        if val is None:
            return ""
        return str(val)

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, body)


def get_active_template_body(message_type: str) -> Optional[str]:
    """First active CommunicationTemplate for this message type, by sort order."""
    tmpl = (
        CommunicationTemplate.objects.filter(message_type=message_type, is_active=True)
        .order_by("sort_order", "id")
        .first()
    )
    if tmpl and (tmpl.body or "").strip():
        return tmpl.body.strip()
    return None


def resolve_parent_for_student_phone(student, phone_raw: str):
    """Match ParentProfile by exact phone string for this student."""
    from apps.tenant.parents.models import ParentStudentLink

    raw = (phone_raw or "").strip()
    if not raw:
        return None
    qs = ParentStudentLink.objects.filter(student=student).select_related("parent")
    for link in qs:
        p = link.parent
        if (getattr(p, "phone", None) or "").strip() == raw:
            return p
    return None


def _fmt_money(amount: Decimal | float | str | None, currency_code: str) -> str:
    """Mirror format_money_for_message without importing services (avoid import cycles)."""
    if amount is None:
        return "—"
    code = (currency_code or "UGX").strip().upper() or "UGX"
    try:
        val = Decimal(str(amount))
    except Exception:
        return str(amount)
    if code == "UGX":
        return f"{code} {val:,.0f}"
    return f"{code} {val:,.2f}"


def fee_reminder_context(
    invoice,
    *,
    currency_code: str,
    school_name: str,
    parent=None,
) -> dict[str, Any]:
    from .services import build_parent_invoice_url

    student = invoice.student
    bal = invoice.balance()
    ref = (invoice.reference or f"#{invoice.pk}").strip()
    due = invoice.due_date.isoformat() if invoice.due_date else ""
    due_line = f"Due: {due}." if due else ""
    portal_url = build_parent_invoice_url(invoice)
    parent_name = "Parent"
    if parent is not None:
        parent_name = f"{parent.first_name} {parent.last_name}".strip() or parent_name
    return {
        "school_name": (school_name or "")[:120],
        "student_name": f"{student.first_name} {student.last_name}".strip(),
        "parent_name": parent_name,
        "amount": _fmt_money(bal, currency_code),
        "currency": (currency_code or "UGX").strip().upper(),
        "invoice_ref": ref,
        "due_date": due,
        "due_line": due_line,
        "portal_url": portal_url,
    }


def payment_receipt_context(
    payment,
    *,
    currency_code: str,
    school_name: str,
    parent=None,
) -> dict[str, Any]:
    from .services import build_parent_payment_receipt_url

    invoice = payment.invoice
    student = invoice.student
    ref = (payment.reference or f"PAY-{payment.pk}").strip()
    receipt_url = build_parent_payment_receipt_url(payment)
    parent_name = "Parent"
    if parent is not None:
        parent_name = f"{parent.first_name} {parent.last_name}".strip() or parent_name
    return {
        "school_name": (school_name or "")[:120],
        "student_name": f"{student.first_name} {student.last_name}".strip(),
        "parent_name": parent_name,
        "amount": _fmt_money(payment.amount, currency_code),
        "currency": (currency_code or "UGX").strip().upper(),
        "payment_ref": ref,
        "receipt_url": receipt_url,
    }


def absence_alert_context(
    entry,
    *,
    school_name: str,
    parent=None,
) -> dict[str, Any]:
    student = entry.student
    session = entry.session
    status = (entry.status or "").replace("_", " ").title()
    course_name = getattr(getattr(session, "offering", None), "course", None)
    class_name = getattr(course_name, "name", "") if course_name else ""
    parent_name = "Parent"
    if parent is not None:
        parent_name = f"{parent.first_name} {parent.last_name}".strip() or parent_name
    note = (entry.note or "").strip()[:200]
    return {
        "school_name": (school_name or "")[:120],
        "student_name": f"{student.first_name} {student.last_name}".strip(),
        "parent_name": parent_name,
        "date": session.date.isoformat(),
        "status": status,
        "class_name": class_name,
        "note": note,
    }


def urgent_announcement_context(
    announcement,
    *,
    school_name: str,
    parent=None,
) -> dict[str, Any]:
    parent_name = "Parent"
    if parent is not None:
        parent_name = f"{parent.first_name} {parent.last_name}".strip() or parent_name
    return {
        "school_name": (school_name or "")[:120],
        "parent_name": parent_name,
        "announcement_title": (announcement.title or "").strip(),
        "announcement_body": ((announcement.body or "").strip())[:2000],
    }
