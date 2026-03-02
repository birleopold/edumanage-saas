"""
Campus-specific dashboard and metrics utilities.
"""
from datetime import date, timedelta
from typing import Dict, Optional

from django.db.models import Count, Q
from django.utils import timezone

from apps.tenant.academics.models import Enrollment
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.finance.models import Invoice
from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile


def get_campus_metrics(campus: Campus, date_range_days: int = 30) -> Dict:
    """
    Get comprehensive metrics for a specific campus.
    
    Args:
        campus: Campus object
        date_range_days: Number of days to include in date-range metrics
    
    Returns:
        Dictionary of campus metrics
    """
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=date_range_days)
    date_range = (start_date, end_date)
    
    metrics = {
        'campus_name': campus.name,
        'campus_id': campus.id,
        'date_range_start': start_date,
        'date_range_end': end_date,
    }
    
    # Student metrics
    students_qs = StudentProfile.objects.filter(campus=campus)
    metrics['students_total'] = students_qs.count()
    metrics['students_active'] = students_qs.filter(is_active=True).count()
    metrics['students_created_in_range'] = students_qs.filter(
        created_at__date__range=date_range
    ).count()
    
    # Teacher metrics
    teachers_qs = TeacherProfile.objects.filter(campus=campus)
    metrics['teachers_total'] = teachers_qs.count()
    metrics['teachers_active'] = teachers_qs.filter(is_active=True).count()
    
    # Enrollment metrics
    enrollments_qs = Enrollment.objects.filter(campus=campus)
    metrics['enrollments_total'] = enrollments_qs.count()
    metrics['enrollments_active'] = enrollments_qs.filter(status=Enrollment.ACTIVE).count()
    metrics['enrollments_dropped'] = enrollments_qs.filter(status=Enrollment.DROPPED).count()
    metrics['enrollments_created_in_range'] = enrollments_qs.filter(
        created_at__date__range=date_range
    ).count()
    
    # Attendance metrics
    sessions_qs = AttendanceSession.objects.filter(
        offering__campus=campus,
        date__range=date_range
    )
    metrics['attendance_sessions_in_range'] = sessions_qs.count()
    
    entries_qs = AttendanceEntry.objects.filter(
        session__offering__campus=campus,
        session__date__range=date_range
    )
    metrics['attendance_entries_in_range'] = entries_qs.count()
    metrics['attendance_present_in_range'] = entries_qs.filter(
        status=AttendanceEntry.PRESENT
    ).count()
    metrics['attendance_absent_in_range'] = entries_qs.filter(
        status=AttendanceEntry.ABSENT
    ).count()
    
    # Calculate attendance rate
    if metrics['attendance_entries_in_range'] > 0:
        metrics['attendance_rate'] = round(
            (metrics['attendance_present_in_range'] / metrics['attendance_entries_in_range']) * 100,
            2
        )
    else:
        metrics['attendance_rate'] = 0
    
    # Finance metrics
    invoices_qs = Invoice.objects.filter(student__campus=campus)
    metrics['invoices_total'] = invoices_qs.count()
    metrics['invoices_created_in_range'] = invoices_qs.filter(
        created_at__date__range=date_range
    ).count()
    
    # Status breakdown
    metrics['invoices_draft'] = invoices_qs.filter(status=Invoice.DRAFT).count()
    metrics['invoices_sent'] = invoices_qs.filter(status=Invoice.SENT).count()
    metrics['invoices_paid'] = invoices_qs.filter(status=Invoice.PAID).count()
    metrics['invoices_overdue'] = invoices_qs.filter(status=Invoice.OVERDUE).count()
    
    return metrics


def get_all_campuses_summary() -> list:
    """
    Get summary metrics for all active campuses.
    
    Returns:
        List of dictionaries with campus summary data
    """
    campuses = Campus.objects.filter(is_active=True).order_by('name')
    summaries = []
    
    for campus in campuses:
        summary = {
            'campus_id': campus.id,
            'campus_name': campus.name,
            'students_total': StudentProfile.objects.filter(campus=campus).count(),
            'students_active': StudentProfile.objects.filter(campus=campus, is_active=True).count(),
            'teachers_total': TeacherProfile.objects.filter(campus=campus).count(),
            'teachers_active': TeacherProfile.objects.filter(campus=campus, is_active=True).count(),
            'enrollments_active': Enrollment.objects.filter(
                campus=campus,
                status=Enrollment.ACTIVE
            ).count(),
        }
        summaries.append(summary)
    
    return summaries


def compare_campuses(campus_ids: list, date_range_days: int = 30) -> Dict:
    """
    Compare metrics across multiple campuses.
    
    Args:
        campus_ids: List of campus IDs to compare
        date_range_days: Number of days for date-range metrics
    
    Returns:
        Dictionary with comparison data
    """
    campuses = Campus.objects.filter(id__in=campus_ids, is_active=True)
    
    comparison = {
        'campuses': [],
        'date_range_days': date_range_days,
    }
    
    for campus in campuses:
        metrics = get_campus_metrics(campus, date_range_days)
        comparison['campuses'].append(metrics)
    
    return comparison
