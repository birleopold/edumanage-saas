"""
Bulk operations for academic data with campus validation.
"""
from typing import List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import CourseOffering, Enrollment


class BulkEnrollmentResult:
    """Result of bulk enrollment operation."""
    
    def __init__(self):
        self.created = []
        self.skipped = []
        self.errors = []
    
    @property
    def success_count(self) -> int:
        return len(self.created)
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def bulk_enroll_students(
    offering: CourseOffering,
    student_ids: List[int],
    validate_campus: bool = True
) -> BulkEnrollmentResult:
    """
    Bulk enroll students in a course offering with campus validation.
    
    Args:
        offering: The course offering to enroll students in
        student_ids: List of student profile IDs to enroll
        validate_campus: If True, validate campus consistency
    
    Returns:
        BulkEnrollmentResult with created, skipped, and error details
    """
    result = BulkEnrollmentResult()
    
    with transaction.atomic():
        students = StudentProfile.objects.filter(id__in=student_ids).select_related('campus')
        
        for student in students:
            try:
                # Check if already enrolled
                if Enrollment.objects.filter(offering=offering, student=student).exists():
                    result.skipped.append({
                        'student_id': student.id,
                        'student_name': str(student),
                        'reason': 'Already enrolled'
                    })
                    continue
                
                # Validate campus consistency
                if validate_campus:
                    if offering.campus and student.campus:
                        if offering.campus != student.campus:
                            result.errors.append({
                                'student_id': student.id,
                                'student_name': str(student),
                                'error': f'Campus mismatch: student is in {student.campus}, offering is in {offering.campus}'
                            })
                            continue
                
                # Create enrollment
                enrollment = Enrollment(
                    offering=offering,
                    student=student,
                    campus=offering.campus or student.campus,
                    status=Enrollment.ACTIVE
                )
                enrollment.save()
                
                result.created.append({
                    'enrollment_id': enrollment.id,
                    'student_id': student.id,
                    'student_name': str(student)
                })
                
            except ValidationError as e:
                result.errors.append({
                    'student_id': student.id,
                    'student_name': str(student),
                    'error': str(e)
                })
            except Exception as e:
                result.errors.append({
                    'student_id': student.id,
                    'student_name': str(student),
                    'error': f'Unexpected error: {str(e)}'
                })
    
    return result


def bulk_transfer_students_campus(
    student_ids: List[int],
    target_campus: Campus,
    update_enrollments: bool = True
) -> Tuple[int, List[dict]]:
    """
    Bulk transfer students to a different campus.
    
    Args:
        student_ids: List of student profile IDs to transfer
        target_campus: The campus to transfer students to
        update_enrollments: If True, also update enrollment campus
    
    Returns:
        Tuple of (success_count, errors_list)
    """
    success_count = 0
    errors = []
    
    with transaction.atomic():
        students = StudentProfile.objects.filter(id__in=student_ids)
        
        for student in students:
            try:
                old_campus = student.campus
                student.campus = target_campus
                student.save(update_fields=['campus'])
                
                if update_enrollments:
                    # Update active enrollments to new campus
                    enrollments = Enrollment.objects.filter(
                        student=student,
                        status=Enrollment.ACTIVE
                    )
                    
                    for enrollment in enrollments:
                        # Only update if offering is also in target campus or has no campus
                        if not enrollment.offering.campus or enrollment.offering.campus == target_campus:
                            enrollment.campus = target_campus
                            enrollment.save(update_fields=['campus'])
                
                success_count += 1
                
            except Exception as e:
                errors.append({
                    'student_id': student.id,
                    'student_name': str(student),
                    'error': str(e)
                })
    
    return success_count, errors


def bulk_transfer_teachers_campus(
    teacher_ids: List[int],
    target_campus: Campus,
    update_offerings: bool = True
) -> Tuple[int, List[dict]]:
    """
    Bulk transfer teachers to a different campus.
    
    Args:
        teacher_ids: List of teacher profile IDs to transfer
        target_campus: The campus to transfer teachers to
        update_offerings: If True, also update offering campus
    
    Returns:
        Tuple of (success_count, errors_list)
    """
    success_count = 0
    errors = []
    
    with transaction.atomic():
        teachers = TeacherProfile.objects.filter(id__in=teacher_ids)
        
        for teacher in teachers:
            try:
                old_campus = teacher.campus
                teacher.campus = target_campus
                teacher.save(update_fields=['campus'])
                
                if update_offerings:
                    # Update active offerings to new campus
                    offerings = CourseOffering.objects.filter(
                        teacher=teacher,
                        is_active=True
                    )
                    
                    for offering in offerings:
                        # Only update if class_group is also in target campus or has no campus
                        if not offering.class_group or not offering.class_group.campus or offering.class_group.campus == target_campus:
                            offering.campus = target_campus
                            offering.save(update_fields=['campus'])
                
                success_count += 1
                
            except Exception as e:
                errors.append({
                    'teacher_id': teacher.id,
                    'teacher_name': str(teacher),
                    'error': str(e)
                })
    
    return success_count, errors


def bulk_create_offerings_for_campus(
    course_ids: List[int],
    term_id: int,
    campus: Campus,
    class_group_id: Optional[int] = None,
    teacher_id: Optional[int] = None
) -> Tuple[int, List[dict]]:
    """
    Bulk create course offerings for a campus.
    
    Args:
        course_ids: List of course IDs to create offerings for
        term_id: Academic term ID
        campus: Campus to create offerings for
        class_group_id: Optional class group ID
        teacher_id: Optional teacher ID
    
    Returns:
        Tuple of (success_count, errors_list)
    """
    from .models import AcademicTerm, ClassGroup, Course
    
    success_count = 0
    errors = []
    
    try:
        term = AcademicTerm.objects.get(id=term_id)
        class_group = ClassGroup.objects.get(id=class_group_id) if class_group_id else None
        teacher = TeacherProfile.objects.get(id=teacher_id) if teacher_id else None
        
        # Validate campus consistency
        if class_group and class_group.campus and class_group.campus != campus:
            errors.append({
                'error': f'Class group campus ({class_group.campus}) does not match target campus ({campus})'
            })
            return 0, errors
        
        if teacher and teacher.campus and teacher.campus != campus:
            errors.append({
                'error': f'Teacher campus ({teacher.campus}) does not match target campus ({campus})'
            })
            return 0, errors
        
    except Exception as e:
        errors.append({'error': f'Invalid parameters: {str(e)}'})
        return 0, errors
    
    with transaction.atomic():
        courses = Course.objects.filter(id__in=course_ids)
        
        for course in courses:
            try:
                # Check if offering already exists
                if CourseOffering.objects.filter(
                    course=course,
                    term=term,
                    campus=campus,
                    class_group=class_group
                ).exists():
                    errors.append({
                        'course_id': course.id,
                        'course_name': str(course),
                        'error': 'Offering already exists'
                    })
                    continue
                
                offering = CourseOffering(
                    course=course,
                    term=term,
                    campus=campus,
                    class_group=class_group,
                    teacher=teacher,
                    is_active=True
                )
                offering.save()
                success_count += 1
                
            except Exception as e:
                errors.append({
                    'course_id': course.id,
                    'course_name': str(course),
                    'error': str(e)
                })
    
    return success_count, errors
