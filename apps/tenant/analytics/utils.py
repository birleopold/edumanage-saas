from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, Course, GradeRange, GradingScale
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.attendance.models import AttendanceEntry, AttendanceSession
from apps.tenant.discipline.models import Incident
from apps.tenant.exams.models import ExamPaper, ExamScore
from apps.tenant.students.models import StudentProfile

from .models import (
    AtRiskAlert,
    ClassPerformanceReport,
    PerformanceTrend,
    StudentPerformanceSnapshot,
    SubjectPerformance,
    TeacherPerformanceMetrics,
)


def calculate_gpa(scores: List[Dict], grading_scale: Optional[GradingScale] = None) -> Optional[Decimal]:
    """Calculate GPA from a list of scores with grade points"""
    if not scores:
        return None
    
    if not grading_scale:
        grading_scale = GradingScale.objects.filter(is_default=True, is_active=True).first()
        if not grading_scale:
            return None
    
    total_points = Decimal(0)
    total_credits = 0
    
    for score_data in scores:
        percentage = score_data.get("percentage")
        credits = score_data.get("credits", 1)
        
        if percentage is None:
            continue
        
        grade_range = grading_scale.ranges.filter(
            min_score__lte=percentage,
            max_score__gte=percentage
        ).first()
        
        if grade_range and grade_range.grade_point:
            total_points += grade_range.grade_point * Decimal(credits)
            total_credits += credits
    
    if total_credits == 0:
        return None
    
    return round(total_points / Decimal(total_credits), 2)


def get_grade_for_percentage(percentage: Decimal, grading_scale: Optional[GradingScale] = None) -> Tuple[str, Optional[Decimal]]:
    """Get grade and grade point for a percentage score"""
    if not grading_scale:
        grading_scale = GradingScale.objects.filter(is_default=True, is_active=True).first()
        if not grading_scale:
            return ("", None)
    
    grade_range = grading_scale.ranges.filter(
        min_score__lte=percentage,
        max_score__gte=percentage
    ).first()
    
    if grade_range:
        return (grade_range.grade, grade_range.grade_point)
    
    return ("", None)


def calculate_student_performance_snapshot(student: StudentProfile, term: AcademicTerm) -> StudentPerformanceSnapshot:
    """Generate comprehensive performance snapshot for a student in a term"""
    
    snapshot, created = StudentPerformanceSnapshot.objects.get_or_create(
        student=student,
        term=term,
        defaults={"stream": student.stream}
    )
    
    # Get all exam scores for the term
    exam_scores = ExamScore.objects.filter(
        student=student,
        paper__exam__term=term,
        score__isnull=False
    ).select_related("paper__offering__course")
    
    # Get assessment scores
    assessment_scores = AssessmentScore.objects.filter(
        student=student,
        assessment__offering__term=term,
        score__isnull=False
    ).select_related("assessment__offering__course")
    
    # Calculate subject-wise performance
    subject_data = {}
    courses = set()
    
    for exam_score in exam_scores:
        course = exam_score.paper.offering.course
        courses.add(course)
        
        if course.id not in subject_data:
            subject_data[course.id] = {
                "course": course,
                "offering": exam_score.paper.offering,
                "exam_scores": [],
                "assessment_scores": [],
            }
        
        percentage = (exam_score.score / exam_score.paper.max_score * 100) if exam_score.paper.max_score else None
        subject_data[course.id]["exam_scores"].append({
            "score": exam_score.score,
            "max_score": exam_score.paper.max_score,
            "percentage": percentage,
        })
    
    for assessment_score in assessment_scores:
        course = assessment_score.assessment.offering.course
        courses.add(course)
        
        if course.id not in subject_data:
            subject_data[course.id] = {
                "course": course,
                "offering": assessment_score.assessment.offering,
                "exam_scores": [],
                "assessment_scores": [],
            }
        
        percentage = (assessment_score.score / assessment_score.assessment.max_score * 100) if assessment_score.assessment.max_score else None
        subject_data[course.id]["assessment_scores"].append({
            "score": assessment_score.score,
            "max_score": assessment_score.assessment.max_score,
            "percentage": percentage,
        })
    
    # Calculate aggregated metrics for each subject
    gpa_scores = []
    passed_count = 0
    failed_count = 0
    grading_scale = GradingScale.objects.filter(is_default=True, is_active=True).first()
    
    for course_id, data in subject_data.items():
        course = data["course"]
        
        # Calculate assessment average
        assessment_avg = None
        if data["assessment_scores"]:
            valid_scores = [s["percentage"] for s in data["assessment_scores"] if s["percentage"] is not None]
            if valid_scores:
                assessment_avg = sum(valid_scores) / len(valid_scores)
        
        # Get exam score
        exam_score = None
        if data["exam_scores"]:
            valid_scores = [s["percentage"] for s in data["exam_scores"] if s["percentage"] is not None]
            if valid_scores:
                exam_score = sum(valid_scores) / len(valid_scores)
        
        # Calculate final score (weighted if both available)
        if assessment_avg is not None and exam_score is not None:
            final_percentage = (assessment_avg * Decimal(0.4) + exam_score * Decimal(0.6))
        elif exam_score is not None:
            final_percentage = exam_score
        elif assessment_avg is not None:
            final_percentage = assessment_avg
        else:
            final_percentage = None
        
        if final_percentage is not None:
            grade, grade_point = get_grade_for_percentage(Decimal(final_percentage), grading_scale)
            is_passed = final_percentage >= 50
            
            # Create/update SubjectPerformance
            SubjectPerformance.objects.update_or_create(
                snapshot=snapshot,
                course=course,
                defaults={
                    "offering": data.get("offering"),
                    "assessment_average": Decimal(assessment_avg) if assessment_avg else None,
                    "exam_score": Decimal(exam_score) if exam_score else None,
                    "final_score": Decimal(final_percentage),
                    "percentage": Decimal(final_percentage),
                    "grade": grade,
                    "grade_point": grade_point,
                    "is_passed": is_passed,
                    "is_weak_area": final_percentage < 60,
                }
            )
            
            if is_passed:
                passed_count += 1
            else:
                failed_count += 1
            
            gpa_scores.append({
                "percentage": final_percentage,
                "credits": course.credits or 1,
            })
    
    # Calculate overall metrics
    total_subjects = len(subject_data)
    snapshot.total_subjects = total_subjects
    snapshot.subjects_passed = passed_count
    snapshot.subjects_failed = failed_count
    
    # Calculate GPA
    snapshot.gpa = calculate_gpa(gpa_scores, grading_scale)
    
    # Calculate overall percentage
    if gpa_scores:
        snapshot.overall_percentage = sum(s["percentage"] for s in gpa_scores) / len(gpa_scores)
    
    # Calculate rankings
    if student.stream:
        calculate_rankings_for_stream(student.stream, term)
    
    # Calculate attendance percentage
    total_sessions = AttendanceSession.objects.filter(
        offering__term=term,
        offering__class_group=student.stream.class_group if student.stream else None
    ).count()
    
    if total_sessions > 0:
        attended = AttendanceEntry.objects.filter(
            student=student,
            session__offering__term=term,
            status="PRESENT"
        ).count()
        snapshot.attendance_percentage = (attended / total_sessions) * 100
    
    # Count discipline incidents
    snapshot.discipline_incidents = Incident.objects.filter(
        student=student,
        incident_date__gte=term.start_date,
        incident_date__lte=term.end_date
    ).count() if term.start_date and term.end_date else 0
    
    # Assess risk
    assess_student_risk(snapshot)
    
    # Check for performance trend
    previous_snapshot = StudentPerformanceSnapshot.objects.filter(
        student=student,
        term__year=term.year,
        term__order__lt=term.order
    ).order_by("-term__order").first()
    
    if previous_snapshot and previous_snapshot.gpa and snapshot.gpa:
        snapshot.previous_gpa = previous_snapshot.gpa
        snapshot.gpa_change = snapshot.gpa - previous_snapshot.gpa
        
        if snapshot.gpa_change > Decimal(0.2):
            snapshot.performance_trend = "IMPROVING"
        elif snapshot.gpa_change < Decimal(-0.2):
            snapshot.performance_trend = "DECLINING"
        else:
            snapshot.performance_trend = "STABLE"
    
    snapshot.save()
    
    # Record trend data
    PerformanceTrend.objects.update_or_create(
        student=student,
        term=term,
        course=None,
        defaults={
            "percentage": snapshot.overall_percentage,
            "gpa": snapshot.gpa,
            "rank": snapshot.class_rank,
        }
    )
    
    return snapshot


def calculate_rankings_for_stream(stream, term: AcademicTerm):
    """Calculate rankings for all students in a stream"""
    snapshots = StudentPerformanceSnapshot.objects.filter(
        term=term,
        stream=stream,
        gpa__isnull=False
    ).order_by("-gpa", "-overall_percentage")
    
    stream_size = snapshots.count()
    
    for rank, snapshot in enumerate(snapshots, start=1):
        snapshot.stream_rank = rank
        snapshot.stream_size = stream_size
        
        # Also calculate class rank (across all streams in class group)
        class_snapshots = StudentPerformanceSnapshot.objects.filter(
            term=term,
            stream__class_group=stream.class_group,
            gpa__isnull=False
        ).order_by("-gpa", "-overall_percentage")
        
        class_size = class_snapshots.count()
        class_rank = list(class_snapshots.values_list("id", flat=True)).index(snapshot.id) + 1
        
        snapshot.class_rank = class_rank
        snapshot.class_size = class_size
        snapshot.calculate_percentile()
        snapshot.save()


def assess_student_risk(snapshot: StudentPerformanceSnapshot):
    """Assess if student is at risk and determine risk level"""
    risk_factors = []
    risk_score = 0
    
    # Academic performance risk
    if snapshot.gpa:
        if snapshot.gpa < Decimal(2.0):
            risk_factors.append("GPA below 2.0 (Failing)")
            risk_score += 3
        elif snapshot.gpa < Decimal(2.5):
            risk_factors.append("GPA below 2.5 (Below Average)")
            risk_score += 2
    
    # Failing subjects
    if snapshot.subjects_failed > 0:
        risk_factors.append(f"Failing {snapshot.subjects_failed} subject(s)")
        risk_score += snapshot.subjects_failed
    
    # Declining trend
    if snapshot.performance_trend == "DECLINING":
        risk_factors.append("Performance declining")
        risk_score += 1
    
    # Poor attendance
    if snapshot.attendance_percentage and snapshot.attendance_percentage < 75:
        risk_factors.append(f"Low attendance ({snapshot.attendance_percentage:.1f}%)")
        risk_score += 2
    
    # Discipline issues
    if snapshot.discipline_incidents > 2:
        risk_factors.append(f"{snapshot.discipline_incidents} discipline incidents")
        risk_score += 1
    
    # Determine risk level
    snapshot.risk_factors = risk_factors
    
    if risk_score >= 6:
        snapshot.risk_level = "CRITICAL"
        snapshot.is_at_risk = True
    elif risk_score >= 4:
        snapshot.risk_level = "HIGH"
        snapshot.is_at_risk = True
    elif risk_score >= 2:
        snapshot.risk_level = "MEDIUM"
        snapshot.is_at_risk = True
    elif risk_score > 0:
        snapshot.risk_level = "LOW"
        snapshot.is_at_risk = False
    else:
        snapshot.risk_level = ""
        snapshot.is_at_risk = False
    
    snapshot.save()
    
    # Create alert for high/critical risk
    if snapshot.risk_level in ["HIGH", "CRITICAL"]:
        create_risk_alert(snapshot)


def create_risk_alert(snapshot: StudentPerformanceSnapshot):
    """Create an at-risk alert for a student"""
    title = f"At-Risk Student: {snapshot.student}"
    description = f"{snapshot.student} is showing {snapshot.risk_level.lower()} risk indicators in {snapshot.term}.\n\n"
    description += "Risk Factors:\n" + "\n".join(f"• {factor}" for factor in snapshot.risk_factors)
    
    recommended_actions = "Recommended Actions:\n"
    recommended_actions += "• Schedule parent-teacher meeting\n"
    recommended_actions += "• Provide additional tutoring support\n"
    recommended_actions += "• Monitor attendance closely\n"
    recommended_actions += "• Develop individualized learning plan\n"
    
    # Check if alert already exists for this snapshot
    existing_alert = AtRiskAlert.objects.filter(
        student=snapshot.student,
        snapshot=snapshot,
        status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"]
    ).first()
    
    if not existing_alert:
        alert = AtRiskAlert.objects.create(
            student=snapshot.student,
            snapshot=snapshot,
            severity=snapshot.risk_level,
            title=title,
            description=description,
            risk_factors=snapshot.risk_factors,
            recommended_actions=recommended_actions,
            assigned_to=snapshot.stream.class_teacher if snapshot.stream else None,
        )
        return alert
    else:
        # Update existing alert
        existing_alert.severity = snapshot.risk_level
        existing_alert.description = description
        existing_alert.risk_factors = snapshot.risk_factors
        existing_alert.save()
        return existing_alert


def generate_class_performance_report(stream, term: AcademicTerm) -> ClassPerformanceReport:
    """Generate aggregated performance report for a class/stream"""
    report, created = ClassPerformanceReport.objects.get_or_create(
        stream=stream,
        term=term
    )
    
    snapshots = StudentPerformanceSnapshot.objects.filter(
        stream=stream,
        term=term
    )
    
    report.total_students = snapshots.count()
    
    # Calculate GPA statistics
    gpa_stats = snapshots.filter(gpa__isnull=False).aggregate(
        avg=Avg("gpa"),
        max=Max("gpa"),
        min=Min("gpa")
    )
    
    report.average_gpa = gpa_stats["avg"]
    report.highest_gpa = gpa_stats["max"]
    report.lowest_gpa = gpa_stats["min"]
    
    # Calculate percentage statistics
    percentage_stats = snapshots.filter(overall_percentage__isnull=False).aggregate(
        avg=Avg("overall_percentage")
    )
    
    report.average_percentage = percentage_stats["avg"]
    
    # Performance distribution
    report.students_excellent = snapshots.filter(gpa__gte=Decimal(3.5)).count()
    report.students_good = snapshots.filter(gpa__gte=Decimal(3.0), gpa__lt=Decimal(3.5)).count()
    report.students_average = snapshots.filter(gpa__gte=Decimal(2.5), gpa__lt=Decimal(3.0)).count()
    report.students_below_average = snapshots.filter(gpa__gte=Decimal(2.0), gpa__lt=Decimal(2.5)).count()
    report.students_failing = snapshots.filter(gpa__lt=Decimal(2.0)).count()
    
    # At-risk statistics
    report.at_risk_count = snapshots.filter(is_at_risk=True).count()
    report.critical_risk_count = snapshots.filter(risk_level="CRITICAL").count()
    
    # Subject performance analysis
    subject_performances = SubjectPerformance.objects.filter(
        snapshot__in=snapshots
    ).values("course__name").annotate(
        avg_percentage=Avg("percentage")
    ).order_by("-avg_percentage")
    
    report.best_performing_subjects = list(subject_performances[:3])
    report.worst_performing_subjects = list(subject_performances.order_by("avg_percentage")[:3])
    
    report.save()
    
    return report


def calculate_teacher_performance_metrics(teacher, term: AcademicTerm, course: Optional[Course] = None):
    """Calculate performance metrics for a teacher"""
    from apps.tenant.academics.models import CourseOffering
    
    offerings = CourseOffering.objects.filter(
        teacher=teacher,
        term=term
    )
    
    if course:
        offerings = offerings.filter(course=course)
    
    for offering in offerings:
        metrics, created = TeacherPerformanceMetrics.objects.get_or_create(
            teacher=teacher,
            term=term,
            course=offering.course
        )
        
        # Get student scores
        exam_scores = ExamScore.objects.filter(
            paper__offering=offering,
            score__isnull=False
        )
        
        assessment_scores = AssessmentScore.objects.filter(
            assessment__offering=offering,
            score__isnull=False
        )
        
        # Calculate metrics
        total_students = exam_scores.values("student").distinct().count()
        metrics.total_students = total_students
        
        if total_students > 0:
            # Average score
            exam_avg = exam_scores.aggregate(avg=Avg("percentage"))["avg"] or 0
            assessment_avg = assessment_scores.aggregate(
                avg=Avg(Sum("score") / Sum("assessment__max_score") * 100)
            )["avg"] or 0
            
            metrics.average_student_score = (exam_avg + assessment_avg) / 2 if assessment_avg else exam_avg
            
            # Pass rate
            passed = exam_scores.filter(paper__passing_score__isnull=False).filter(
                score__gte=models.F("paper__passing_score")
            ).values("student").distinct().count()
            metrics.pass_rate = (passed / total_students) * 100 if total_students > 0 else 0
            
            # Excellence rate (>= 80%)
            excellent = exam_scores.filter(percentage__gte=80).values("student").distinct().count()
            metrics.excellence_rate = (excellent / total_students) * 100 if total_students > 0 else 0
        
        # Assessment activity
        assessments = Assessment.objects.filter(offering=offering)
        metrics.total_assessments = assessments.count()
        metrics.assessments_published = assessments.filter(is_published=True).count()
        
        metrics.save()


def export_student_performance_report(student: StudentProfile, term: AcademicTerm) -> Dict:
    """Export comprehensive performance report for a student"""
    snapshot = StudentPerformanceSnapshot.objects.filter(
        student=student,
        term=term
    ).first()
    
    if not snapshot:
        return {}
    
    subject_performances = SubjectPerformance.objects.filter(
        snapshot=snapshot
    ).select_related("course")
    
    trends = PerformanceTrend.objects.filter(
        student=student,
        term__year=term.year
    ).order_by("term__order")
    
    return {
        "student": {
            "name": str(student),
            "student_id": student.student_id,
            "stream": str(student.stream) if student.stream else "",
        },
        "term": str(term),
        "overall_performance": {
            "gpa": float(snapshot.gpa) if snapshot.gpa else None,
            "percentage": float(snapshot.overall_percentage) if snapshot.overall_percentage else None,
            "class_rank": snapshot.class_rank,
            "class_size": snapshot.class_size,
            "percentile": float(snapshot.percentile) if snapshot.percentile else None,
        },
        "subject_performance": [
            {
                "course": sp.course.name,
                "score": float(sp.final_score) if sp.final_score else None,
                "percentage": float(sp.percentage) if sp.percentage else None,
                "grade": sp.grade,
                "rank": sp.subject_rank,
                "is_passed": sp.is_passed,
            }
            for sp in subject_performances
        ],
        "trends": [
            {
                "term": str(trend.term),
                "gpa": float(trend.gpa) if trend.gpa else None,
                "percentage": float(trend.percentage) if trend.percentage else None,
            }
            for trend in trends
        ],
        "attendance": {
            "percentage": float(snapshot.attendance_percentage) if snapshot.attendance_percentage else None,
        },
        "risk_assessment": {
            "is_at_risk": snapshot.is_at_risk,
            "risk_level": snapshot.risk_level,
            "risk_factors": snapshot.risk_factors,
        },
    }
