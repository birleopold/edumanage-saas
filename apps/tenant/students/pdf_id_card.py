"""
Printable student ID card PDF (credit-card style, ReportLab).
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ISO ID-1 (CR80) landscape: 3.375" x 2.125"
CARD_W = 3.375 * inch
CARD_H = 2.125 * inch


def generate_student_id_card_pdf(*, student, org):
    """
    org: OrganizationProfile (name).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(CARD_W, CARD_H),
        leftMargin=0.2 * inch,
        rightMargin=0.2 * inch,
        topMargin=0.15 * inch,
        bottomMargin=0.15 * inch,
        title="Student ID",
    )
    styles = getSampleStyleSheet()
    school = (getattr(org, "name", None) or "School").strip()
    elements = []

    elements.append(Paragraph(f"<b>{school}</b> <font size=8>Student ID</font>", styles["Normal"]))
    elements.append(Spacer(1, 0.08 * inch))
    name = f"{student.first_name} {student.last_name}".strip()
    elements.append(Paragraph(f"<b><font size=14>{name}</font></b>", styles["Normal"]))
    elements.append(Spacer(1, 0.06 * inch))

    sid = (getattr(student, "student_id", None) or "").strip() or f"#{student.pk}"
    campus = str(student.campus) if getattr(student, "campus_id", None) else "—"
    rows = [
        ["Student no.", sid],
        ["Campus", campus[:48]],
    ]
    t = Table(rows, colWidths=[0.95 * inch, 2.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(t)
    elements.append(Spacer(1, 0.05 * inch))
    elements.append(Paragraph("<i>Not valid unless signed/stamped by the school.</i>", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
