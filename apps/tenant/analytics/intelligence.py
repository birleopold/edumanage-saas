from decimal import Decimal
from statistics import median

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, CourseOffering, Enrollment
from apps.tenant.assessments.models import Assessment, AssessmentScore
from apps.tenant.attendance.models import AttendanceEntry
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import AtRiskAlert, ClassPerformanceReport, PerformanceTrend, StudentPerformanceSnapshot, SubjectPerformance, TeacherPerformanceMetrics
from .intelligence_models import AnalyticsRun, Intervention, ReportCardCommentSuggestion, StudentRecommendation


PASS_MARK = Decimal("50")
EXCELLENCE_MARK = Decimal("80")


def pct(score, max_score):
    if score is None or not max_score:
        return None
    return (Decimal(score) / Decimal(max_score)) * Decimal("100")


def grade_for_percentage(value):
    if value is None:
        return ""
    value = Decimal(value)
    if value >= 80:
        return "A"
    if value >= 70:
        return "B"
    if value >= 60:
        return "C"
    if value >= 50:
        return "D"
    return "F"


def gpa_for_percentage(value):
    if value is None:
        return None
    value = Decimal(value)
    if value >= 80:
        return Decimal("4.00")
    if value >= 70:
        return Decimal("3.50")
    if value >= 60:
        return Decimal("3.00")
    if value >= 50:
        return Decimal("2.00")
    return Decimal("1.00")


def student_attendance_percentage(student, term):
    qs = AttendanceEntry.objects.filter(student=student, session__offering__term=term)
    total = qs.count()
    if not total:
        return None
    present = qs.filter(status__in=[AttendanceEntry.PRESENT, AttendanceEntry.LATE]).count()
    return (Decimal(present) / Decimal(total)) * Decimal("100")


def offering_student_percentage(offering, student):
    scores = AssessmentScore.objects.filter(assessment__offering=offering, student=student, score__isnull=False, assessment__is_published=True).select_related("assessment")
    values = [pct(s.score, s.assessment.max_score) for s in scores]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def risk_profile(overall, attendance, failed_count, gpa_change):
    factors = []
    score = 0
    if overall is not None and overall < 50:
        factors.append("Overall average below pass mark")
        score += 3
    if failed_count >= 3:
        factors.append("Failed three or more subjects")
        score += 3
    elif failed_count > 0:
        factors.append("Failed one or more subjects")
        score += 1
    if attendance is not None and attendance < 75:
        factors.append("Attendance below 75%")
        score += 2
    if gpa_change is not None and gpa_change < Decimal("-0.50"):
        factors.append("Performance declined significantly")
        score += 2
    if score >= 6:
        return True, "CRITICAL", factors
    if score >= 4:
        return True, "HIGH", factors
    if score >= 2:
        return True, "MEDIUM", factors
    if score >= 1:
        return True, "LOW", factors
    return False, "", factors


def recommendations_for_snapshot(snapshot):
    recs = []
    weak_subjects = list(snapshot.subject_performances.filter(is_weak_area=True).select_related("course"))
    for sp in weak_subjects:
        recs.append((sp.course, f"Arrange focused revision and weekly practice tasks in {sp.course.name}."))
    if snapshot.attendance_percentage is not None and snapshot.attendance_percentage < 75:
        recs.append((None, "Follow up on attendance with parent/guardian and agree on daily attendance support."))
    if snapshot.overall_percentage is not None and snapshot.overall_percentage < 50:
        recs.append((None, "Create a two-week remedial plan with short assignments and teacher check-ins."))
    return recs


def comment_for_snapshot(snapshot):
    strong = [sp.course.name for sp in snapshot.subject_performances.filter(is_weak_area=False).order_by("-percentage")[:2]]
    weak = [sp.course.name for sp in snapshot.subject_performances.filter(is_weak_area=True).order_by("percentage")[:3]]
    name = snapshot.student.first_name or "The learner"
    trend = (snapshot.performance_trend or "STABLE").lower()
    parts = [f"{name} has shown {trend} performance this term"]
    if snapshot.overall_percentage is not None:
        parts.append(f"with an overall average of {snapshot.overall_percentage:.1f}%")
    if strong:
        parts.append(f"Strengths include {', '.join(strong)}")
    if weak:
        parts.append(f"More support is needed in {', '.join(weak)}")
    if snapshot.attendance_percentage is not None and snapshot.attendance_percentage < 75:
        parts.append("Improved attendance will support better learning outcomes")
    return ". ".join(parts) + "."


@transaction.atomic
def generate_student_snapshot(student, term):
    offerings = CourseOffering.objects.filter(term=term, enrollment__student=student, enrollment__status=Enrollment.ACTIVE).select_related("course", "teacher").distinct()
    subject_results = []
    for offering in offerings:
        percent = offering_student_percentage(offering, student)
        if percent is None:
            continue
        subject_results.append((offering, percent, gpa_for_percentage(percent)))
    total_subjects = len(subject_results)
    passed = len([x for x in subject_results if x[1] >= PASS_MARK])
    failed = total_subjects - passed
    overall = (sum([x[1] for x in subject_results], Decimal("0")) / Decimal(total_subjects)) if total_subjects else None
    gpa_values = [x[2] for x in subject_results if x[2] is not None]
    gpa = (sum(gpa_values, Decimal("0")) / Decimal(len(gpa_values))) if gpa_values else None
    previous = StudentPerformanceSnapshot.objects.filter(student=student).exclude(term=term).order_by("-term__year__name", "-term__order").first()
    previous_gpa = previous.gpa if previous else None
    gpa_change = (gpa - previous_gpa) if gpa is not None and previous_gpa is not None else None
    trend = "STABLE"
    if gpa_change is not None and gpa_change > Decimal("0.25"):
        trend = "IMPROVING"
    elif gpa_change is not None and gpa_change < Decimal("-0.25"):
        trend = "DECLINING"
    attendance = student_attendance_percentage(student, term)
    is_risk, risk_level, risk_factors = risk_profile(overall, attendance, failed, gpa_change)
    snapshot, _ = StudentPerformanceSnapshot.objects.update_or_create(student=student, term=term, defaults={"stream": student.stream, "gpa": gpa, "overall_percentage": overall, "total_subjects": total_subjects, "subjects_passed": passed, "subjects_failed": failed, "previous_gpa": previous_gpa, "gpa_change": gpa_change, "performance_trend": trend, "attendance_percentage": attendance, "is_at_risk": is_risk, "risk_level": risk_level, "risk_factors": risk_factors})
    snapshot.subject_performances.all().delete()
    for offering, percent, grade_point in subject_results:
        SubjectPerformance.objects.create(snapshot=snapshot, course=offering.course, offering=offering, assessment_average=percent, final_score=percent, percentage=percent, grade=grade_for_percentage(percent), grade_point=grade_point, is_passed=percent >= PASS_MARK, is_weak_area=percent < PASS_MARK)
        PerformanceTrend.objects.update_or_create(student=student, term=term, course=offering.course, defaults={"score": percent, "percentage": percent, "grade": grade_for_percentage(percent), "gpa": grade_point})
    PerformanceTrend.objects.update_or_create(student=student, term=term, course=None, defaults={"score": overall, "percentage": overall, "grade": grade_for_percentage(overall), "gpa": gpa})
    generate_alerts_recommendations_and_comment(snapshot)
    return snapshot


def generate_alerts_recommendations_and_comment(snapshot):
    alert = None
    if snapshot.is_at_risk:
        title = f"{snapshot.risk_level.title()} academic risk"
        description = "; ".join(snapshot.risk_factors) or "Student requires academic follow-up."
        alert, _ = AtRiskAlert.objects.update_or_create(student=snapshot.student, snapshot=snapshot, status=AtRiskAlert.OPEN, defaults={"severity": snapshot.risk_level or AtRiskAlert.LOW, "risk_factors": snapshot.risk_factors, "title": title, "description": description, "recommended_actions": "Review attendance, weak subjects, and arrange learner support."})
    for course, text in recommendations_for_snapshot(snapshot):
        StudentRecommendation.objects.update_or_create(student=snapshot.student, snapshot=snapshot, subject=course, defaults={"alert": alert, "title": "Learner support recommendation", "recommendation": text, "priority": snapshot.risk_level or "MEDIUM"})
    weak = [sp.course.name for sp in snapshot.subject_performances.filter(is_weak_area=True)]
    strengths = [sp.course.name for sp in snapshot.subject_performances.filter(is_weak_area=False).order_by("-percentage")[:3]]
    ReportCardCommentSuggestion.objects.update_or_create(student=snapshot.student, term=snapshot.term, defaults={"snapshot": snapshot, "comment": comment_for_snapshot(snapshot), "strengths": strengths, "weak_areas": weak, "recommendations": [r[1] for r in recommendations_for_snapshot(snapshot)]})
    return alert


def rank_snapshots(term):
    streams = set(StudentPerformanceSnapshot.objects.filter(term=term, stream__isnull=False).values_list("stream_id", flat=True))
    for stream_id in streams:
        snaps = list(StudentPerformanceSnapshot.objects.filter(term=term, stream_id=stream_id).order_by("-overall_percentage"))
        size = len(snaps)
        for index, snap in enumerate(snaps, start=1):
            snap.stream_rank = index
            snap.class_rank = index
            snap.stream_size = size
            snap.class_size = size
            snap.percentile = Decimal(str(((size - index + 1) / size) * 100)) if size else None
            snap.save(update_fields=["stream_rank", "class_rank", "stream_size", "class_size", "percentile"])


def generate_class_reports(term):
    count = 0
    streams = set(StudentPerformanceSnapshot.objects.filter(term=term, stream__isnull=False).values_list("stream_id", flat=True))
    for stream_id in streams:
        snaps = list(StudentPerformanceSnapshot.objects.filter(term=term, stream_id=stream_id))
        if not snaps:
            continue
        gpas = [s.gpa for s in snaps if s.gpa is not None]
        avgs = [s.overall_percentage for s in snaps if s.overall_percentage is not None]
        ClassPerformanceReport.objects.update_or_create(stream_id=stream_id, term=term, defaults={"total_students": len(snaps), "average_gpa": sum(gpas, Decimal("0")) / Decimal(len(gpas)) if gpas else None, "average_percentage": sum(avgs, Decimal("0")) / Decimal(len(avgs)) if avgs else None, "median_gpa": Decimal(str(median(gpas))) if gpas else None, "highest_gpa": max(gpas) if gpas else None, "lowest_gpa": min(gpas) if gpas else None, "students_excellent": len([s for s in snaps if s.gpa and s.gpa >= Decimal("3.5")]), "students_good": len([s for s in snaps if s.gpa and Decimal("3.0") <= s.gpa < Decimal("3.5")]), "students_average": len([s for s in snaps if s.gpa and Decimal("2.5") <= s.gpa < Decimal("3.0")]), "students_below_average": len([s for s in snaps if s.gpa and Decimal("2.0") <= s.gpa < Decimal("2.5")]), "students_failing": len([s for s in snaps if s.gpa and s.gpa < Decimal("2.0")]), "at_risk_count": len([s for s in snaps if s.is_at_risk]), "critical_risk_count": len([s for s in snaps if s.risk_level == "CRITICAL"])})
        count += 1
    return count


def generate_teacher_metrics(term):
    count = 0
    for offering in CourseOffering.objects.filter(term=term, teacher__isnull=False).select_related("teacher", "course"):
        scores = AssessmentScore.objects.filter(assessment__offering=offering, score__isnull=False, assessment__is_published=True).select_related("assessment")
        values = [pct(s.score, s.assessment.max_score) for s in scores]
        values = [v for v in values if v is not None]
        if not values:
            continue
        avg = sum(values, Decimal("0")) / Decimal(len(values))
        TeacherPerformanceMetrics.objects.update_or_create(teacher=offering.teacher, term=term, course=offering.course, defaults={"total_students": Enrollment.objects.filter(offering=offering, status=Enrollment.ACTIVE).count(), "average_student_score": avg, "pass_rate": Decimal(len([v for v in values if v >= PASS_MARK])) / Decimal(len(values)) * Decimal("100"), "excellence_rate": Decimal(len([v for v in values if v >= EXCELLENCE_MARK])) / Decimal(len(values)) * Decimal("100"), "total_assessments": Assessment.objects.filter(offering=offering).count(), "assessments_published": Assessment.objects.filter(offering=offering, is_published=True).count()})
        count += 1
    return count


@transaction.atomic
def run_analytics(term=None, run_type=AnalyticsRun.MANUAL):
    term = term or AcademicTerm.objects.filter(is_current=True).first() or AcademicTerm.objects.order_by("-year__name", "-order").first()
    run = AnalyticsRun.objects.create(term=term, run_type=run_type)
    try:
        students = StudentProfile.objects.filter(is_active=True)
        if term:
            students = students.filter(enrollment__offering__term=term, enrollment__status=Enrollment.ACTIVE).distinct()
        snapshot_count = 0
        for student in students:
            generate_student_snapshot(student, term)
            snapshot_count += 1
        rank_snapshots(term)
        class_count = generate_class_reports(term)
        teacher_count = generate_teacher_metrics(term)
        alert_count = AtRiskAlert.objects.filter(snapshot__term=term, status=AtRiskAlert.OPEN).count()
        run.generated_snapshots = snapshot_count
        run.generated_alerts = alert_count
        run.generated_class_reports = class_count
        run.generated_teacher_metrics = teacher_count
        run.status = AnalyticsRun.SUCCESS
        run.finished_at = timezone.now()
        run.save()
    except Exception as exc:
        run.status = AnalyticsRun.FAILED
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save()
        raise
    return run


def attendance_performance_correlation(term):
    rows = list(StudentPerformanceSnapshot.objects.filter(term=term, attendance_percentage__isnull=False, overall_percentage__isnull=False).values_list("attendance_percentage", "overall_percentage"))
    if len(rows) < 2:
        return {"count": len(rows), "correlation": None}
    xs = [float(x[0]) for x in rows]
    ys = [float(x[1]) for x in rows]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    denom_y = sum((y - my) ** 2 for y in ys) ** 0.5
    return {"count": len(rows), "correlation": numerator / (denom_x * denom_y) if denom_x and denom_y else None}
