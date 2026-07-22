from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.utils import timezone
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.tenant.assessments.result_facade import (
    build_result_snapshot,
    course_result_rows,
)

from .models import ECDObservation, ReportTemplate, ResultPolicy
from .uace_services import calculate_uace_points


def _q(value, places="0.01"):
    return Decimal(str(value or 0)).quantize(
        Decimal(places),
        rounding=ROUND_HALF_UP,
    )


def resolve_report_template(student):
    level_id = getattr(
        getattr(getattr(student, "stream", None), "class_group", None),
        "level_id",
        None,
    )
    qs = ReportTemplate.objects.filter(is_active=True)
    candidates = [
        qs.filter(campus_id=student.campus_id, level_id=level_id, is_default=True),
        qs.filter(campus_id=student.campus_id, level__isnull=True, is_default=True),
        qs.filter(campus__isnull=True, level_id=level_id, is_default=True),
        qs.filter(campus__isnull=True, level__isnull=True, is_default=True),
    ]
    for candidate in candidates:
        obj = candidate.order_by("-stage_id", "pk").first()
        if obj:
            return obj
    return None


def resolve_result_policy(student):
    class_group = getattr(getattr(student, "stream", None), "class_group", None)
    level_id = getattr(class_group, "level_id", None)
    program_id = getattr(class_group, "program_id", None)
    qs = ResultPolicy.objects.filter(is_active=True)
    rows = list(
        qs.filter(
            campus_id__in=(None, student.campus_id),
            level_id__in=(None, level_id),
            program_id__in=(None, program_id),
        )
    )
    rows.sort(
        key=lambda row: (
            row.priority,
            bool(row.campus_id),
            bool(row.level_id),
            bool(row.program_id),
            row.is_default,
        ),
        reverse=True,
    )
    return rows[0] if rows else None


def course_results(student, term=None):
    """Return the same weighted and graded course rows used by every portal."""

    snapshot = build_result_snapshot(student, academic_term=term)
    return course_result_rows(snapshot)


def academic_summary(student, term=None):
    snapshot = build_result_snapshot(student, academic_term=term)
    results = course_result_rows(snapshot)
    policy = resolve_result_policy(student)
    system = policy.result_system if policy else ResultPolicy.GENERIC
    settings = dict(policy.settings or {}) if policy else {}
    mean = snapshot.overall_percentage or Decimal("0")
    summary = {
        "system": system,
        "mean": mean,
        "result_count": len(results),
        "overall_grade": snapshot.overall_grade,
        "overall_remark": snapshot.overall_remark,
        "is_complete": snapshot.is_complete,
    }
    if snapshot.promotion_status:
        summary["promotion_status"] = snapshot.promotion_status

    if system in {ResultPolicy.PLE, ResultPolicy.UCE}:
        ordered = sorted(
            [row for row in results if row["percentage"] is not None],
            key=lambda row: row["percentage"],
            reverse=True,
        )
        best_count = int(
            settings.get(
                "aggregate_subject_count",
                4 if system == ResultPolicy.PLE else 8,
            )
        )
        grade_values = settings.get(
            "aggregate_grade_values",
            {
                "D1": 1,
                "D2": 2,
                "C3": 3,
                "C4": 4,
                "C5": 5,
                "C6": 6,
                "P7": 7,
                "P8": 8,
                "F9": 9,
            },
        )
        aggregate = sum(
            int(grade_values.get(row["grade"], 9))
            for row in ordered[:best_count]
        )
        bands = settings.get(
            "division_bands",
            [
                {"max": 12, "label": "Division 1"},
                {"max": 24, "label": "Division 2"},
                {"max": 28, "label": "Division 3"},
                {"max": 32, "label": "Division 4"},
            ],
        )
        division = next(
            (
                band["label"]
                for band in bands
                if aggregate <= int(band["max"])
            ),
            "Ungraded",
        )
        summary.update({"aggregate": aggregate, "division": division})
    elif system == ResultPolicy.UACE:
        academic_year = getattr(term, "year", None) if term else None
        uace = calculate_uace_points(
            student,
            results,
            academic_year=academic_year,
            settings=settings,
        )
        summary.update(
            {
                "principal_points": uace["principal_points"],
                "subsidiary_points": uace["subsidiary_points"],
                "total_points": uace["total_points"],
                "uace_configured": uace["configured"],
                "uace_incomplete": uace["incomplete"],
                "uace_reason": uace.get("reason", ""),
                "subject_points": uace.get("subject_points", []),
            }
        )
        if uace["incomplete"]:
            summary["is_complete"] = False
    elif system == ResultPolicy.GPA:
        weighted = Decimal("0")
        credits = Decimal("0")
        for row in results:
            if row["grade_point"] is None:
                continue
            weighted += Decimal(row["grade_point"]) * Decimal(row["credits"])
            credits += Decimal(row["credits"])
        summary.update(
            {
                "gpa": _q(weighted / credits) if credits else Decimal("0"),
                "credits": credits,
            }
        )
    return summary


def cumulative_gpa(student):
    snapshot = build_result_snapshot(student)
    rows = course_result_rows(snapshot)
    weighted = Decimal("0")
    credits = Decimal("0")
    for row in rows:
        if row["grade_point"] is None:
            continue
        course_credits = Decimal(row["credits"])
        weighted += Decimal(row["grade_point"]) * course_credits
        credits += course_credits
    return _q(weighted / credits) if credits else Decimal("0")


def qr_drawing(data: str, size=28 * mm):
    widget = QrCodeWidget(data)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(
        size,
        size,
        transform=[size / width, 0, 0, size / height, 0, 0],
    )
    drawing.add(widget)
    return drawing


def permit_pdf(permit, verify_url):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PermitTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1e3a8a"),
    )
    story = [Paragraph(permit.title, title_style), Spacer(1, 8 * mm)]
    rows = [
        ["Reference", permit.reference],
        ["Learner", permit.student.get_full_name()],
        ["Student number", permit.student.student_id or "—"],
        ["Permit type", permit.get_permit_type_display()],
        [
            "Valid from",
            timezone.localtime(permit.valid_from).strftime("%d %b %Y %H:%M"),
        ],
        [
            "Valid until",
            timezone.localtime(permit.valid_until).strftime("%d %b %Y %H:%M")
            if permit.valid_until
            else "No fixed expiry",
        ],
        ["Status", "VALID" if permit.is_valid else permit.get_status_display().upper()],
    ]
    table = Table(rows, colWidths=[45 * mm, 105 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 8 * mm),
            qr_drawing(verify_url),
            Paragraph(
                "Scan to verify this document against the live institution record.",
                styles["BodyText"],
            ),
        ]
    )
    doc.build(story)
    buffer.seek(0)
    return buffer


def transcript_pdf(student, verify_url, term=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Academic Transcript", styles["Title"]),
        Paragraph(
            f"{student.get_full_name()} — {student.student_id or 'No student number'}",
            styles["Heading2"],
        ),
        Spacer(1, 4 * mm),
    ]
    results = course_results(student, term)
    rows = [["Course", "Credits", "Percentage", "Grade", "Grade point"]]
    for row in results:
        rows.append(
            [
                row["course"].name,
                row["credits"],
                row["percentage"] if row["percentage"] is not None else "—",
                row["grade"] or "—",
                row["grade_point"] if row["grade_point"] is not None else "—",
            ]
        )
    table = Table(
        rows,
        repeatRows=1,
        colWidths=[75 * mm, 20 * mm, 28 * mm, 20 * mm, 25 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 5 * mm),
            Paragraph(
                f"Cumulative GPA: <b>{cumulative_gpa(student)}</b>",
                styles["Heading3"],
            ),
            qr_drawing(verify_url, 24 * mm),
            Paragraph(
                "Verification code is linked to the live academic record.",
                styles["BodyText"],
            ),
        ]
    )
    doc.build(story)
    buffer.seek(0)
    return buffer


def report_pdf(student, verify_url, term=None):
    buffer = BytesIO()
    template = resolve_report_template(student)
    sections = (
        template.sections
        if template and template.sections
        else ["identity", "results", "attendance", "ecd", "comments", "signatures"]
    )
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(
            template.title if template else "Learner Progress Report",
            styles["Title"],
        )
    ]
    results = course_results(student, term)
    summary = academic_summary(student, term)
    for section in sections:
        if section == "identity":
            story.extend(
                [
                    Paragraph("Learner details", styles["Heading2"]),
                    Paragraph(
                        f"Name: <b>{student.get_full_name()}</b><br/>"
                        f"Student number: {student.student_id or '—'}<br/>"
                        f"Class: {getattr(student.stream, 'class_group', '—')}<br/>"
                        f"Stream: {student.stream or '—'}",
                        styles["BodyText"],
                    ),
                ]
            )
        elif section == "results":
            rows = [["Subject / course", "Percentage", "Grade", "Remark"]]
            rows.extend(
                [
                    row["course"].name,
                    row["percentage"] if row["percentage"] is not None else "—",
                    row["grade"] or "—",
                    row["remark"] or "—",
                ]
                for row in results
            )
            table = Table(
                rows,
                repeatRows=1,
                colWidths=[75 * mm, 30 * mm, 22 * mm, 42 * mm],
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("PADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            summary_text = ", ".join(
                f"{key.replace('_', ' ').title()} {value}"
                for key, value in summary.items()
                if key not in {"system", "result_count", "subject_points"}
            )
            story.extend(
                [
                    Paragraph("Academic results", styles["Heading2"]),
                    table,
                    Paragraph("Overall: " + summary_text, styles["BodyText"]),
                ]
            )
        elif section == "ecd":
            observations = ECDObservation.objects.filter(student=student)
            if term:
                observations = observations.filter(academic_term=term)
            rows = [["Development domain", "Rating", "Observation"]]
            rows.extend(
                [
                    row.get_domain_display(),
                    row.get_rating_display(),
                    row.observation or "—",
                ]
                for row in observations
            )
            story.extend(
                [
                    Paragraph("Developmental observations", styles["Heading2"]),
                    Table(
                        rows,
                        repeatRows=1,
                        colWidths=[45 * mm, 35 * mm, 90 * mm],
                        style=TableStyle(
                            [
                                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
                                ("PADDING", (0, 0), (-1, -1), 5),
                            ]
                        ),
                    ),
                ]
            )
        elif section == "comments":
            story.extend(
                [
                    Paragraph("Comments", styles["Heading2"]),
                    Paragraph(
                        "Class teacher: ________________________________________________"
                        "<br/><br/>Head teacher / principal: ______________________________________",
                        styles["BodyText"],
                    ),
                ]
            )
        elif section == "signatures":
            story.extend(
                [
                    Spacer(1, 8 * mm),
                    Paragraph(
                        "Class teacher signature ____________________ &nbsp;&nbsp;&nbsp; "
                        "Head teacher signature ____________________",
                        styles["BodyText"],
                    ),
                ]
            )
        elif section == "attendance":
            story.extend(
                [
                    Paragraph("Attendance", styles["Heading2"]),
                    Paragraph(
                        "Attendance information is drawn from the institution's attendance register for the selected academic period.",
                        styles["BodyText"],
                    ),
                ]
            )
        elif section == "activities":
            story.extend(
                [
                    Paragraph("Clubs, sports and activities", styles["Heading2"]),
                    Paragraph(
                        "Participation and achievements are retained in the learner's co-curricular record.",
                        styles["BodyText"],
                    ),
                ]
            )
        elif section == "finance":
            story.extend(
                [
                    Paragraph("Fees and clearance", styles["Heading2"]),
                    Paragraph(
                        "Financial clearance is evaluated from live invoices, payments and approved exceptions.",
                        styles["BodyText"],
                    ),
                ]
            )
        story.append(Spacer(1, 4 * mm))
    story.extend(
        [
            qr_drawing(verify_url, 22 * mm),
            Paragraph(
                "Scan to verify this report against the live institution record.",
                styles["BodyText"],
            ),
        ]
    )
    doc.build(story)
    buffer.seek(0)
    return buffer
