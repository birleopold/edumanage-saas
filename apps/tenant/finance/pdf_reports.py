from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet


def simple_report_pdf(title, headers, rows):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 0.2 * inch)]
    story.append(Table([headers] + rows, repeatRows=1))
    doc.build(story)
    buffer.seek(0)
    return buffer


def trial_balance_pdf(rows):
    return simple_report_pdf("Trial Balance", ["Code", "Account", "Debit", "Credit", "Balance"], [[r["account"].code, r["account"].name, str(r["debit_total"]), str(r["credit_total"]), str(r["balance"])] for r in rows])


def cash_flow_pdf(report):
    return simple_report_pdf("Cash Flow", ["Account", "Cash In", "Cash Out", "Net"], [[r["cash_account"].name, str(r["cash_in"]), str(r["cash_out"]), str(r["net"])] for r in report["rows"]])
