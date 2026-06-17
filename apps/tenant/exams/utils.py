from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_admit_card_pdf(seat_allocation):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("<b>EXAMINATION ADMIT CARD</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))
    data = [
        ["Student Name:", seat_allocation.student.get_full_name()],
        ["Student ID:", seat_allocation.student.student_id],
        ["Exam:", str(seat_allocation.schedule.paper.exam)],
        ["Subject:", seat_allocation.schedule.paper.offering.course.name],
        ["Date:", seat_allocation.schedule.date.strftime("%d %B %Y")],
        ["Time:", f"{seat_allocation.schedule.start_time.strftime('%I:%M %p')} - {seat_allocation.schedule.end_time.strftime('%I:%M %p')}"],
        ["Room:", seat_allocation.schedule.room_name],
        ["Seat Number:", seat_allocation.seat_number],
    ]
    table = Table(data, colWidths=[2 * inch, 4 * inch])
    table.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (1, 0), (1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 11), ("BOTTOMPADDING", (0, 0), (-1, -1), 12), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    elements.append(table)
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph("<b>Instructions:</b>", styles["Heading3"]))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("1. Report to the examination hall 15 minutes before the start time.<br/>2. Carry this admit card and your student ID card.<br/>3. Mobile phones and unauthorized devices are prohibited.<br/>4. Follow all instructions given by the invigilator.<br/>", styles["Normal"]))
    doc.build(elements)
    buffer.seek(0)
    return buffer


def auto_grade_attempt(attempt):
    from .services import score_attempt
    total, _manual_pending = score_attempt(attempt)
    return total


def generate_exam_report_card_pdf(*, student, exam, scores, org=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []
    school_name = getattr(org, "name", "School") if org else "School"
    elements.append(Paragraph(f"<b>{school_name}</b>", styles["Title"]))
    elements.append(Paragraph("<b>EXAM REPORT CARD</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))
    student_rows = [
        ["Student", student.get_full_name()],
        ["Student ID", student.student_id],
        ["Exam", str(exam)],
        ["Campus", str(getattr(student, "campus", "") or "-")],
    ]
    info = Table(student_rows, colWidths=[1.5 * inch, 5 * inch])
    info.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    elements.append(info)
    elements.append(Spacer(1, 0.25 * inch))
    rows = [["Subject", "Score", "Percentage", "Grade", "Rank", "Comment"]]
    total_score = Decimal("0")
    total_max = Decimal("0")
    for score in scores:
        max_score = score.paper.max_score or Decimal("0")
        total_max += max_score
        total_score += score.score or Decimal("0")
        rows.append([
            score.paper.offering.course.name,
            f"{score.score or 0} / {max_score}",
            f"{score.percentage or 0:.1f}%" if score.percentage is not None else "-",
            score.grade or "-",
            score.rank or "-",
            score.note or "",
        ])
    overall = (total_score / total_max * 100) if total_max else Decimal("0")
    rows.append(["TOTAL / AVERAGE", f"{total_score} / {total_max}", f"{overall:.1f}%", "", "", ""])
    table = Table(rows, colWidths=[2.0 * inch, 1.1 * inch, 1.0 * inch, 0.75 * inch, 0.65 * inch, 1.6 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer


def calculate_exam_analytics(paper):
    from .models import ExamAnalytics
    analytics, _created = ExamAnalytics.objects.get_or_create(paper=paper)
    analytics.refresh_analytics()
    return analytics


def allocate_seats_auto(schedule, students, seat_prefix=""):
    from .models import SeatAllocation
    allocations = []
    available = schedule.available_seats()
    if len(students) > available:
        raise ValueError(f"Not enough seats. Available: {available}, Requested: {len(students)}")
    for idx, student in enumerate(students, start=1):
        seat_number = f"{seat_prefix}{idx}"
        allocation, created = SeatAllocation.objects.get_or_create(schedule=schedule, student=student, defaults={"seat_number": seat_number})
        if created:
            allocations.append(allocation)
    return allocations


def calculate_student_rank(paper):
    from .models import ExamScore
    scores = ExamScore.objects.filter(paper=paper, score__isnull=False).order_by("-score", "student__last_name")
    current_rank = 1
    previous_score = None
    for idx, score_obj in enumerate(scores, start=1):
        if previous_score is None or score_obj.score < previous_score:
            current_rank = idx
        score_obj.rank = current_rank
        score_obj.save(update_fields=["rank"])
        previous_score = score_obj.score


def assign_grades(paper, grade_boundaries):
    from .models import ExamScore
    scores = ExamScore.objects.filter(paper=paper, score__isnull=False)
    for score_obj in scores:
        score_obj.calculate_percentage()
        if score_obj.percentage is not None:
            grade = "F"
            for grade_letter, min_percentage in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                if score_obj.percentage >= min_percentage:
                    grade = grade_letter
                    break
            score_obj.grade = grade
            score_obj.save(update_fields=["grade", "percentage"])
