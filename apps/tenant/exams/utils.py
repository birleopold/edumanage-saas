from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_admit_card_pdf(seat_allocation):
    """Generate admit card PDF for a student"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("<b>EXAMINATION ADMIT CARD</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # Student and exam details
    data = [
        ['Student Name:', seat_allocation.student.get_full_name()],
        ['Student ID:', seat_allocation.student.student_id],
        ['Exam:', str(seat_allocation.schedule.paper.exam)],
        ['Subject:', seat_allocation.schedule.paper.offering.course.name],
        ['Date:', seat_allocation.schedule.date.strftime('%d %B %Y')],
        ['Time:', f"{seat_allocation.schedule.start_time.strftime('%I:%M %p')} - {seat_allocation.schedule.end_time.strftime('%I:%M %p')}"],
        ['Room:', seat_allocation.schedule.room_name],
        ['Seat Number:', seat_allocation.seat_number],
    ]
    
    table = Table(data, colWidths=[2*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Instructions
    instructions = Paragraph("<b>Instructions:</b>", styles['Heading3'])
    elements.append(instructions)
    elements.append(Spacer(1, 0.1*inch))
    
    inst_text = """
    1. Report to the examination hall 15 minutes before the start time.<br/>
    2. Carry this admit card and your student ID card.<br/>
    3. Mobile phones and electronic devices are strictly prohibited.<br/>
    4. Follow all instructions given by the invigilator.<br/>
    """
    
    inst_para = Paragraph(inst_text, styles['Normal'])
    elements.append(inst_para)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def auto_grade_attempt(attempt):
    """Automatically grade an online exam attempt for objective questions"""
    from .models import StudentResponse
    
    responses = StudentResponse.objects.filter(attempt=attempt).select_related('exam_question__question')
    total_marks = Decimal(0)
    
    for response in responses:
        if response.auto_grade():
            if response.marks_awarded:
                total_marks += response.marks_awarded
    
    attempt.score = total_marks
    attempt.status = attempt.GRADED
    attempt.save()
    
    return total_marks


def calculate_exam_analytics(paper):
    """Calculate and update exam analytics for a paper"""
    from .models import ExamAnalytics
    
    analytics, created = ExamAnalytics.objects.get_or_create(paper=paper)
    analytics.refresh_analytics()
    return analytics


def allocate_seats_auto(schedule, students, seat_prefix=''):
    """Automatically allocate seats to students"""
    from .models import SeatAllocation
    
    allocations = []
    available = schedule.available_seats()
    
    if len(students) > available:
        raise ValueError(f"Not enough seats. Available: {available}, Requested: {len(students)}")
    
    for idx, student in enumerate(students, start=1):
        seat_number = f"{seat_prefix}{idx}"
        
        allocation, created = SeatAllocation.objects.get_or_create(
            schedule=schedule,
            student=student,
            defaults={'seat_number': seat_number}
        )
        
        if created:
            allocations.append(allocation)
    
    return allocations


def calculate_student_rank(paper):
    """Calculate and update rank for all students in a paper"""
    from .models import ExamScore
    
    scores = ExamScore.objects.filter(paper=paper, score__isnull=False).order_by('-score', 'student__last_name')
    
    current_rank = 1
    previous_score = None
    
    for idx, score_obj in enumerate(scores, start=1):
        if previous_score is None or score_obj.score < previous_score:
            current_rank = idx
        
        score_obj.rank = current_rank
        score_obj.save(update_fields=['rank'])
        previous_score = score_obj.score


def assign_grades(paper, grade_boundaries):
    """
    Assign letter grades based on percentage boundaries
    grade_boundaries: dict like {'A': 90, 'B': 80, 'C': 70, 'D': 60, 'E': 50}
    """
    from .models import ExamScore
    
    scores = ExamScore.objects.filter(paper=paper, score__isnull=False)
    
    for score_obj in scores:
        score_obj.calculate_percentage()
        
        if score_obj.percentage:
            grade = 'F'
            for grade_letter, min_percentage in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                if score_obj.percentage >= min_percentage:
                    grade = grade_letter
                    break
            
            score_obj.grade = grade
            score_obj.save(update_fields=['grade', 'percentage'])
