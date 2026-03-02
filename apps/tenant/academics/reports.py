from decimal import Decimal
from typing import Dict, List, Optional

from django.db.models import Q

from apps.tenant.academics.grading import (
    calculate_term_average,
    calculate_weighted_average,
    get_class_rank,
    get_letter_grade,
)
from apps.tenant.academics.models import AcademicTerm, Enrollment, GradingScale
from apps.tenant.students.models import StudentProfile


class ReportCard:
    def __init__(self, student_id: int, term_id: int, grading_scale_id: Optional[int] = None):
        self.student = StudentProfile.objects.select_related('campus', 'stream__class_group').get(id=student_id)
        self.term = AcademicTerm.objects.select_related('year').get(id=term_id)
        
        if grading_scale_id:
            self.grading_scale = GradingScale.objects.prefetch_related('ranges').get(id=grading_scale_id)
        else:
            self.grading_scale = GradingScale.objects.filter(is_default=True).prefetch_related('ranges').first()
        
        self.enrollments = Enrollment.objects.filter(
            student_id=student_id,
            offering__term_id=term_id,
            status=Enrollment.ACTIVE
        ).select_related('offering__course', 'offering__teacher__user').order_by('offering__course__name')
        
        self._subject_results = None
        self._summary = None
        self._ranking = None

    def get_subject_results(self) -> List[Dict]:
        if self._subject_results is not None:
            return self._subject_results
        
        results = []
        
        for enrollment in self.enrollments:
            avg_score = calculate_weighted_average(self.student.id, enrollment.offering_id)
            
            grade_info = None
            if avg_score is not None and self.grading_scale:
                grade_range = get_letter_grade(avg_score, self.grading_scale)
                if grade_range:
                    grade_info = {
                        'grade': grade_range.grade,
                        'grade_point': grade_range.grade_point,
                        'remark': grade_range.remark
                    }
            
            results.append({
                'course_name': enrollment.offering.course.name,
                'course_code': enrollment.offering.course.code,
                'teacher': str(enrollment.offering.teacher) if enrollment.offering.teacher else 'N/A',
                'score': round(avg_score, 2) if avg_score is not None else None,
                'grade': grade_info['grade'] if grade_info else 'N/A',
                'grade_point': grade_info['grade_point'] if grade_info else None,
                'remark': grade_info['remark'] if grade_info else '',
            })
        
        self._subject_results = results
        return results

    def get_summary(self) -> Dict:
        if self._summary is not None:
            return self._summary
        
        subject_results = self.get_subject_results()
        
        total_subjects = len(subject_results)
        subjects_with_scores = [r for r in subject_results if r['score'] is not None]
        
        if subjects_with_scores:
            total_score = sum(r['score'] for r in subjects_with_scores)
            average = total_score / len(subjects_with_scores)
            highest = max(r['score'] for r in subjects_with_scores)
            lowest = min(r['score'] for r in subjects_with_scores)
        else:
            average = None
            highest = None
            lowest = None
        
        grade_info = None
        if average is not None and self.grading_scale:
            grade_range = get_letter_grade(Decimal(str(average)), self.grading_scale)
            if grade_range:
                grade_info = {
                    'grade': grade_range.grade,
                    'grade_point': grade_range.grade_point,
                    'remark': grade_range.remark
                }
        
        self._summary = {
            'total_subjects': total_subjects,
            'average': round(average, 2) if average else None,
            'highest': round(highest, 2) if highest else None,
            'lowest': round(lowest, 2) if lowest else None,
            'overall_grade': grade_info['grade'] if grade_info else 'N/A',
            'overall_remark': grade_info['remark'] if grade_info else '',
        }
        
        return self._summary

    def get_ranking(self) -> Dict:
        if self._ranking is not None:
            return self._ranking
        
        stream_id = self.student.stream_id if self.student.stream else None
        self._ranking = get_class_rank(self.student.id, self.term.id, stream_id)
        
        return self._ranking

    def to_dict(self) -> Dict:
        return {
            'student': {
                'id': self.student.student_id,
                'name': str(self.student),
                'stream': str(self.student.stream) if self.student.stream else 'N/A',
                'campus': str(self.student.campus) if self.student.campus else 'N/A',
            },
            'term': {
                'name': str(self.term),
                'year': str(self.term.year),
                'start_date': self.term.start_date,
                'end_date': self.term.end_date,
            },
            'grading_scale': self.grading_scale.name if self.grading_scale else 'N/A',
            'subjects': self.get_subject_results(),
            'summary': self.get_summary(),
            'ranking': self.get_ranking(),
        }


def generate_class_report_cards(term_id: int, stream_id: Optional[int] = None, 
                                class_group_id: Optional[int] = None) -> List[ReportCard]:
    query = Q(
        enrollment__offering__term_id=term_id,
        enrollment__status=Enrollment.ACTIVE,
        is_active=True
    )
    
    if stream_id:
        query &= Q(stream_id=stream_id)
    elif class_group_id:
        query &= Q(stream__class_group_id=class_group_id)
    
    students = StudentProfile.objects.filter(query).distinct().order_by('last_name', 'first_name')
    
    report_cards = []
    for student in students:
        try:
            report_card = ReportCard(student.id, term_id)
            report_cards.append(report_card)
        except Exception:
            continue
    
    return report_cards


def get_term_statistics(term_id: int, stream_id: Optional[int] = None) -> Dict:
    from apps.tenant.academics.grading import calculate_term_average
    
    query = Q(
        enrollment__offering__term_id=term_id,
        enrollment__status=Enrollment.ACTIVE,
        is_active=True
    )
    
    if stream_id:
        query &= Q(stream_id=stream_id)
    
    students = StudentProfile.objects.filter(query).distinct()
    
    averages = []
    for student in students:
        avg = calculate_term_average(student.id, term_id)
        if avg is not None:
            averages.append(avg)
    
    if not averages:
        return {
            'total_students': 0,
            'mean': None,
            'highest': None,
            'lowest': None,
            'pass_rate': None,
        }
    
    mean = sum(averages) / len(averages)
    highest = max(averages)
    lowest = min(averages)
    
    passing = [a for a in averages if a >= Decimal('50')]
    pass_rate = (len(passing) / len(averages)) * 100
    
    return {
        'total_students': len(averages),
        'mean': round(mean, 2),
        'highest': round(highest, 2),
        'lowest': round(lowest, 2),
        'pass_rate': round(pass_rate, 2),
    }
