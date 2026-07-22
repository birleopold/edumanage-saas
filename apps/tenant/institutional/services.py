from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.db.models import Avg, Sum
from django.urls import reverse
from django.utils import timezone
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.tenant.academics.models import GradeRange
from apps.tenant.assessments.models import AssessmentScore
from apps.tenant.exams.models import ExamScore

from .models import ECDObservation, ReportTemplate, ResultPolicy, VerifiablePermit


def _q(value, places="0.01"):
    return Decimal(str(value or 0)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def resolve_report_template(student):
    level_id = getattr(getattr(getattr(student, "stream", None), "class_group", None), "level_id", None)
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
    level_id = getattr(getattr(getattr(student, "stream", None), "class_group", None), "level_id", None)
    program_id = getattr(getattr(getattr(student, "stream", None), "class_group", None), "program_id", None)
    qs = ResultPolicy.objects.filter(is_active=True)
    rows = list(qs.filter(campus_id__in=(None, student.campus_id), level_id__in=(None, level_id), program_id__in=(None, program_id)))
    rows.sort(key=lambda row: (row.priority, bool(row.campus_id), bool(row.level_id), bool(row.program_id), row.is_default), reverse=True)
    return rows[0] if rows else None


def _score_rows(student, term=None):
    assessment_qs = AssessmentScore.objects.filter(student=student, assessment__is_published=True).select_related("assessment", "assessment__offering", "assessment__offering__course")
    exam_qs = ExamScore.objects.filter(student=student, paper__is_published=True).select_related("paper", "paper__offering", "paper__offering__course")
    if term:
        assessment_qs = assessment_qs.filter(assessment__offering__term=term)
        exam_qs = exam_qs.filter(paper__offering__term=term)
    rows = []
    for item in assessment_qs:
        if item.score is None or not item.assessment.max_score:
            continue
        pct = Decimal(item.score) * Decimal("100") / Decimal(item.assessment.max_score)
        rows.append({"course": item.assessment.offering.course, "label": item.assessment.name, "percentage": _q(pct), "source": "Assessment"})
    for item in exam_qs:
        if item.score is None or not item.paper.max_score:
            continue
        pct = Decimal(item.score) * Decimal("100") / Decimal(item.paper.max_score)
        rows.append({"course": item.paper.offering.course, "label": item.paper.offering.course.name, "percentage": _q(pct), "source": "Examination"})
    return rows


def course_results(student, term=None):
    grouped = defaultdict(list)
    for row in _score_rows(student, term):
        grouped[row["course"]].append(row["percentage"])
    results = []
    for course, values in grouped.items():
        average = _q(sum(values) / len(values))
        grade_range = GradeRange.objects.filter(scale__is_active=True, min_score__lte=average, max_score__gte=average).order_by("scale__is_default", "order").last()
        results.append({
            "course": course,
            "percentage": average,
            "grade": grade_range.grade if grade_range else "",
            "remark": grade_range.remark if grade_range else "",
            "grade_point": grade_range.grade_point if grade_range else None,
            "credits": course.credits or 1,
        })
    return sorted(results, key=lambda row: row["course"].name)


def academic_summary(student, term=None):
    results = course_results(student, term)
    policy = resolve_result_policy(student)
    system = policy.result_system if policy else ResultPolicy.GENERIC
    settings = dict(policy.settings or {}) if policy else {}
    percentages = [row["percentage"] for row in results]
    mean = _q(sum(percentages) / len(percentages)) if percentages else Decimal("0")
    summary = {"system": system, "mean": mean, "result_count": len(results)}

    if system in {ResultPolicy.PLE, ResultPolicy.UCE}:
        ordered = sorted(results, key=lambda row: row["percentage"], reverse=True)
        best_count = int(settings.get("aggregate_subject_count", 4 if system == ResultPolicy.PLE else 8))
        grade_values = settings.get("aggregate_grade_values", {"D1": 1, "D2": 2, "C3": 3, "C4": 4, "C5": 5, "C6": 6, "P7": 7, "P8": 8, "F9": 9})
        aggregate = sum(int(grade_values.get(row["grade"], 9)) for row in ordered[:best_count])
        bands = settings.get("division_bands", [{"max": 12, "label": "Division 1"}, {"max": 24, "label": "Division 2"}, {"max": 28, "label": "Division 3"}, {"max": 32, "label": "Division 4"}])
        division = next((band["label"] for band in bands if aggregate <= int(band["max"])), "Ungraded")
        summary.update({"aggregate": aggregate, "division": division})
    elif system == ResultPolicy.UACE:
        grade_points = settings.get("principal_grade_points", {"A": 6, "B": 5, "C": 4, "D": 3, "E": 2, "O": 1, "F": 0})
        principal_count = int(settings.get("principal_subject_count", 3))
        ordered = sorted(results, key=lambda row: row["percentage"], reverse=True)
        principal_points = sum(int(grade_points.get(row["grade"], 0)) for row in ordered[:principal_count])
        subsidiary_points = sum(1 for row in ordered[principal_count:] if row["percentage"] >= Decimal(str(settings.get("subsidiary_pass_percentage", 50))))
        summary.update({"principal_points": principal_points, "subsidiary_points": subsidiary_points, "total_points": principal_points + subsidiary_points})
    elif system == ResultPolicy.GPA:
        weighted = Decimal("0")
        credits = Decimal("0")
        for row in results:
            if row["grade_point"] is None:
                continue
            weighted += Decimal(row["grade_point"]) * Decimal(row["credits"])
            credits += Decimal(row["credits"])
        summary.update({"gpa": _q(weighted / credits) if credits else Decimal("0"), "credits": credits})
    return summary


def cumulative_gpa(student):
    rows = _score_rows(student)
    by_course = defaultdict(list)
    for row in rows:
        by_course[row["course"]].append(row["percentage"])
    weighted = Decimal("0")
    credits = Decimal("0")
    for course, values in by_course.items():
        average = _q(sum(values) / len(values))
        grade_range = GradeRange.objects.filter(scale__is_active=True, min_score__lte=average, max_score__gte=average).order_by("scale__is_default", "order").last()
        if not grade_range or grade_range.grade_point is None:
            continue
        course_credits = Decimal(course.credits or 1)
        weighted += Decimal(grade_range.grade_point) * course_credits
        credits += course_credits
    return _q(weighted / credits) if credits else Decimal("0")


def qr_drawing(data: str, size=28 * mm):
    widget = QrCodeWidget(data)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    return drawing


def permit_pdf(permit, verify_url):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PermitTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#1e3a8a"))
    story = [Paragraph(permit.title, title_style), Spacer(1, 8 * mm)]
    rows = [
        ["Reference", permit.reference],
        ["Learner", permit.student.get_full_name()],
        ["Student number", permit.student.student_id or "—"],
        ["Permit type", permit.get_permit_type_display()],
        ["Valid from", timezone.localtime(permit.valid_from).strftime("%d %b %Y %H:%M")],
        ["Valid until", timezone.localtime(permit.valid_until).strftime("%d %b %Y %H:%M") if permit.valid_until else "No fixed expiry"],
        ["Status", "VALID" if permit.is_valid else permit.get_status_display().upper()],
    ]
    table = Table(rows, colWidths=[45 * mm, 105 * mm])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7)]))
    story.extend([table, Spacer(1, 8 * mm), qr_drawing(verify_url), Paragraph("Scan to verify this document against the live institution record.", styles["BodyText"])])
    doc.build(story)
    buffer.seek(0)
    return buffer


def transcript_pdf(student, verify_url, term=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("Academic Transcript", styles["Title"]), Paragraph(f"{student.get_full_name()} — {student.student_id or 'No student number'}", styles["Heading2"]), Spacer(1, 4 * mm)]
    results = course_results(student, term)
    rows = [["Course", "Credits", "Percentage", "Grade", "Grade point"]]
    for row in results:
        rows.append([row["course"].name, row["credits"], row["percentage"], row["grade"] or "—", row["grade_point"] if row["grade_point"] is not None else "—"])
    table = Table(rows, repeatRows=1, colWidths=[75 * mm, 20 * mm, 28 * mm, 20 * mm, 25 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("PADDING", (0, 0), (-1, -1), 6)]))
    story.extend([table, Spacer(1, 5 * mm), Paragraph(f"Cumulative GPA: <b>{cumulative_gpa(student)}</b>", styles["Heading3"]), qr_drawing(verify_url, 24 * mm), Paragraph("Verification code is linked to the live academic record.", styles["BodyText"])])
    doc.build(story)
    buffer.seek(0)
    return buffer


def report_pdf(student, verify_url, term=None):
    buffer = BytesIO()
    template = resolve_report_template(student)
    sections = template.sections if template and template.sections else ["identity", "results", "attendance", "ecd", "comments", "signatures"]
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(template.title if template else "Learner Progress Report", styles["Title"])]
    results = course_results(student, term)
    summary = academic_summary(student, term)
    for section in sections:
        if section == "identity":
            story.extend([Paragraph("Learner details", styles["Heading2"]), Paragraph(f"Name: <b>{student.get_full_name()}</b><br/>Student number: {student.student_id or '—'}<br/>Class: {getattr(student.stream, 'class_group', '—')}<br/>Stream: {student.stream or '—'}", styles["BodyText"])])
        elif section == "results":
            rows = [["Subject / course", "Percentage", "Grade", "Remark"]] + [[row["course"].name, row["percentage"], row["grade"] or "—", row["remark"] or "—"] for row in results]
            table = Table(rows, repeatRows=1, colWidths=[75 * mm, 30 * mm, 22 * mm, 42 * mm])
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("PADDING", (0, 0), (-1, -1), 6)]))
            story.extend([Paragraph("Academic results", styles["Heading2"]), table, Paragraph("Overall: " + ", ".join(f"{key.replace('_', ' ').title()} {value}" for key, value in summary.items() if key not in {"system", "result_count"}), styles["BodyText"])])
        elif section == "ecd":
            observations = ECDObservation.objects.filter(student=student)
            if term:
                observations = observations.filter(academic_term=term)
            rows = [["Development domain", "Rating", "Observation"]] + [[row.get_domain_display(), row.get_rating_display(), row.observation or "—"] for row in observations]
            story.extend([Paragraph("Developmental observations", styles["Heading2"]), Table(rows, repeatRows=1, colWidths=[45 * mm, 35 * mm, 90 * mm], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")), ("PADDING", (0, 0), (-1, -1), 5)]))])
        elif section == "comments":
            story.extend([Paragraph("Comments", styles["Heading2"]), Paragraph("Class teacher: ________________________________________________<br/><br/>Head teacher / principal: ______________________________________", styles["BodyText"])])
        elif section == "signatures":
            story.extend([Spacer(1, 8 * mm), Paragraph("Class teacher signature ____________________ &nbsp;&nbsp;&nbsp; Head teacher signature ____________________", styles["BodyText"])])
        elif section == "attendance":
            story.extend([Paragraph("Attendance", styles["Heading2"]), Paragraph("Attendance information is drawn from the institution's attendance register for the selected academic period.", styles["BodyText"])])
        elif section == "activities":
            story.extend([Paragraph("Clubs, sports and activities", styles["Heading2"]), Paragraph("Participation and achievements are retained in the learner's co-curricular record.", styles["BodyText"])])
        elif section == "finance":
            story.extend([Paragraph("Fees and clearance", styles["Heading2"]), Paragraph("Financial clearance is evaluated from live invoices, payments and approved exceptions.", styles["BodyText"])])
        story.append(Spacer(1, 4 * mm))
    story.extend([qr_drawing(verify_url, 22 * mm), Paragraph("Scan to verify this report against the live institution record.", styles["BodyText"])])
    doc.build(story)
    buffer.seek(0)
    return buffer
