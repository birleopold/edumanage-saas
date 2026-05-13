"""
Formal admission letter PDF (ReportLab) for admitted applicants.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_admission_letter_pdf(*, applicant, student, org, issued_by: str = ""):
    """
    applicant: Applicant (admitted).
    student: StudentProfile created from admission.
    org: OrganizationProfile (name).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Admission letter")
    styles = getSampleStyleSheet()
    elements = []

    school = (getattr(org, "name", None) or "School").strip()
    elements.append(Paragraph(f"<b>{school}</b>", styles["Title"]))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph("<b>Letter of admission</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    today = student.created_at.strftime("%Y-%m-%d") if getattr(student, "created_at", None) else "—"
    body = (
        f"This letter confirms that <b>{applicant.first_name} {applicant.last_name}</b> "
        f"has been offered a place at <b>{school}</b>."
    )
    elements.append(Paragraph(body, styles["Normal"]))
    elements.append(Spacer(1, 0.15 * inch))

    rows = [
        ["Assigned student number", getattr(student, "student_id", "") or f"#{student.pk}"],
        ["Campus", str(student.campus) if getattr(student, "campus_id", None) else "—"],
        ["Target term", str(applicant.target_term) if applicant.target_term_id else "—"],
        ["Date of issue", today],
    ]
    t = Table(rows, colWidths=[2.0 * inch, 4.0 * inch])
    t.setStyle(
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
    elements.append(t)
    elements.append(Spacer(1, 0.35 * inch))

    elements.append(
        Paragraph(
            "<i>Please bring this letter and valid identification when reporting. "
            "For enquiries, contact the admissions office.</i>",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 0.4 * inch))
    if issued_by:
        elements.append(Paragraph(f"<b>Issued by:</b> {issued_by}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
