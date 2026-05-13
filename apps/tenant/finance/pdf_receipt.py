"""
PDF fee receipts for recorded payments (ReportLab).
"""
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_payment_receipt_pdf(*, payment, org, student_label: str = ""):
    """
    Build a simple official receipt PDF for one Payment row.
    org: OrganizationProfile (name, default_currency).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Payment receipt")
    styles = getSampleStyleSheet()
    elements = []

    inv = payment.invoice
    currency = (getattr(org, "default_currency", None) or "UGX").strip().upper() or "UGX"
    school = (org.name or "School").strip()

    title = Paragraph(f"<b>{school}</b><br/><font size=14>Fee payment receipt</font>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 0.25 * inch))

    meta = [
        ["Receipt no.", f"PAY-{payment.pk}"],
        ["Date issued", payment.created_at.strftime("%Y-%m-%d %H:%M") if payment.created_at else "—"],
        ["Student", student_label or str(inv.student)],
        ["Student ID", getattr(inv.student, "student_id", "") or "—"],
        ["Invoice ref.", inv.reference or f"#{inv.pk}"],
        ["Period", f"{inv.academic_year or '—'} · {inv.academic_term or '—'}"],
    ]
    t1 = Table(meta, colWidths=[1.6 * inch, 4.4 * inch])
    t1.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]
        )
    )
    elements.append(t1)
    elements.append(Spacer(1, 0.2 * inch))

    amt = payment.amount if isinstance(payment.amount, Decimal) else Decimal(str(payment.amount))
    amt_txt = f"{currency} {amt:,.0f}" if currency == "UGX" else f"{currency} {amt:,.2f}"

    pay_rows = [
        ["Amount received", amt_txt],
        ["Method", payment.get_method_display()],
    ]
    if payment.method == payment.MOBILE and payment.mobile_network:
        pay_rows.append(["Mobile network", payment.get_mobile_network_display()])
    pay_rows.append(["Transaction reference", (payment.reference or "—")[:64]])
    pay_rows.append(["Received on", str(payment.received_at or payment.created_at.date())])

    t2 = Table(pay_rows, colWidths=[1.8 * inch, 4.2 * inch])
    t2.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    elements.append(t2)
    elements.append(Spacer(1, 0.35 * inch))

    footer = Paragraph(
        "<i>Generated electronically. Keep for your records. For queries contact the bursary.</i>",
        styles["Normal"],
    )
    elements.append(footer)

    doc.build(elements)
    buffer.seek(0)
    return buffer
