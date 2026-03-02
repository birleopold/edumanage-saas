from decimal import Decimal
from typing import Optional

from django.db.models import Avg, Count, Q, Sum

from apps.tenant.academics.models import GradeRange, GradingScale
from apps.tenant.assessments.models import AssessmentScore
from apps.tenant.exams.models import ExamScore


def get_letter_grade(score: Decimal, grading_scale: GradingScale) -> Optional[GradeRange]:
    if score is None:
        return None
    
    for grade_range in grading_scale.ranges.all():
        if grade_range.contains_score(score):
            return grade_range
    
    return None


def calculate_weighted_average(student_id: int, offering_id: int) -> Optional[Decimal]:
    from apps.tenant.assessments.models import Assessment
    
    assessments = Assessment.objects.filter(
        offering_id=offering_id,
        is_published=True
    ).prefetch_related('scores')
    
    total_weight = Decimal('0')
    weighted_sum = Decimal('0')
    
    for assessment in assessments:
        score_obj = assessment.scores.filter(student_id=student_id).first()
        if score_obj and score_obj.score is not None:
            weight = assessment.weight or Decimal('1')
            percentage = (score_obj.score / assessment.max_score) * Decimal('100')
            weighted_sum += percentage * weight
            total_weight += weight
    
    if total_weight > 0:
        return weighted_sum / total_weight
    
    return None


def calculate_term_average(student_id: int, term_id: int) -> Optional[Decimal]:
    from apps.tenant.academics.models import CourseOffering, Enrollment
    
    enrollments = Enrollment.objects.filter(
        student_id=student_id,
        offering__term_id=term_id,
        status=Enrollment.ACTIVE
    ).select_related('offering')
    
    total_score = Decimal('0')
    course_count = 0
    
    for enrollment in enrollments:
        avg_score = calculate_weighted_average(student_id, enrollment.offering_id)
        if avg_score is not None:
            total_score += avg_score
            course_count += 1
    
    if course_count > 0:
        return total_score / Decimal(course_count)
    
    return None


def calculate_gpa(student_id: int, term_id: int, grading_scale: GradingScale) -> Optional[Decimal]:
    from apps.tenant.academics.models import Enrollment
    
    enrollments = Enrollment.objects.filter(
        student_id=student_id,
        offering__term_id=term_id,
        status=Enrollment.ACTIVE
    ).select_related('offering__course')
    
    total_points = Decimal('0')
    total_credits = Decimal('0')
    
    for enrollment in enrollments:
        avg_score = calculate_weighted_average(student_id, enrollment.offering_id)
        if avg_score is not None:
            grade_range = get_letter_grade(avg_score, grading_scale)
            if grade_range and grade_range.grade_point is not None:
                credits = Decimal(enrollment.offering.course.credits or 1)
                total_points += grade_range.grade_point * credits
                total_credits += credits
    
    if total_credits > 0:
        return total_points / total_credits
    
    return None


def get_class_rank(student_id: int, term_id: int, stream_id: Optional[int] = None) -> dict:
    from apps.tenant.academics.models import Enrollment
    from apps.tenant.students.models import StudentProfile
    
    student_avg = calculate_term_average(student_id, term_id)
    
    if student_avg is None:
        return {
            'rank': None,
            'total_students': 0,
            'average': None,
            'percentile': None
        }
    
    query = Q(
        enrollment__offering__term_id=term_id,
        enrollment__status=Enrollment.ACTIVE,
        is_active=True
    )
    
    if stream_id:
        query &= Q(stream_id=stream_id)
    
    students = StudentProfile.objects.filter(query).distinct()
    
    student_averages = []
    for s in students:
        avg = calculate_term_average(s.id, term_id)
        if avg is not None:
            student_averages.append({
                'student_id': s.id,
                'average': avg
            })
    
    student_averages.sort(key=lambda x: x['average'], reverse=True)
    
    rank = None
    for idx, item in enumerate(student_averages, start=1):
        if item['student_id'] == student_id:
            rank = idx
            break
    
    total_students = len(student_averages)
    percentile = None
    if rank and total_students > 0:
        percentile = ((total_students - rank + 1) / total_students) * 100
    
    return {
        'rank': rank,
        'total_students': total_students,
        'average': student_avg,
        'percentile': round(percentile, 2) if percentile else None
    }


def get_subject_statistics(offering_id: int) -> dict:
    from apps.tenant.assessments.models import Assessment
    
    assessments = Assessment.objects.filter(
        offering_id=offering_id,
        is_published=True
    )
    
    if not assessments.exists():
        return {
            'mean': None,
            'highest': None,
            'lowest': None,
            'pass_rate': None,
            'total_students': 0
        }
    
    all_scores = []
    student_ids = set()
    
    for assessment in assessments:
        scores = assessment.scores.filter(score__isnull=False)
        for score_obj in scores:
            percentage = (score_obj.score / assessment.max_score) * Decimal('100')
            all_scores.append(percentage)
            student_ids.add(score_obj.student_id)
    
    if not all_scores:
        return {
            'mean': None,
            'highest': None,
            'lowest': None,
            'pass_rate': None,
            'total_students': len(student_ids)
        }
    
    mean = sum(all_scores) / len(all_scores)
    highest = max(all_scores)
    lowest = min(all_scores)
    
    passing_scores = [s for s in all_scores if s >= Decimal('50')]
    pass_rate = (len(passing_scores) / len(all_scores)) * 100 if all_scores else 0
    
    return {
        'mean': round(mean, 2),
        'highest': round(highest, 2),
        'lowest': round(lowest, 2),
        'pass_rate': round(pass_rate, 2),
        'total_students': len(student_ids)
    }
