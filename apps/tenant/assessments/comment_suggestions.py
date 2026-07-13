from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from apps.tenant.analytics.intelligence_models import ReportCardCommentSuggestion
from apps.tenant.attendance.models import AttendanceEntry
from apps.tenant.discipline.models import Incident
from apps.tenant.students.models import StudentProfile

from .models import Assessment, AssessmentScore
from .services import percentage


@dataclass(frozen=True)
class ReportCommentSuggestion:
    student: StudentProfile
    comment: str
    performance_band: str
    trend: str
    attendance_percentage: Decimal | None
    discipline_incidents: int
    strengths: list[str]
    weak_areas: list[str]
    recommendations: list[str]


def _student_name(student: StudentProfile) -> str:
    return student.first_name or str(student) or "The learner"


def _band(value: Decimal | None) -> str:
    if value is None:
        return "ungraded"
    if value >= 80:
        return "excellent"
    if value >= 70:
        return "strong"
    if value >= 60:
        return "good"
    if value >= 50:
        return "developing"
    return "support"


def _trend(assessment: Assessment, student: StudentProfile, current_percentage: Decimal | None) -> str:
    if current_percentage is None:
        return "pending"
    qs = AssessmentScore.objects.filter(
        assessment__offering=assessment.offering,
        student=student,
        score__isnull=False,
    ).exclude(assessment=assessment).select_related("assessment")
    if assessment.date:
        qs = qs.filter(Q(assessment__date__lt=assessment.date) | Q(assessment__date=assessment.date, assessment__id__lt=assessment.id))
    else:
        qs = qs.filter(assessment__id__lt=assessment.id)
    previous = qs.order_by("-assessment__date", "-assessment_id").first()
    if not previous:
        return "new"
    previous_percentage = percentage(previous.score, previous.assessment.max_score)
    if previous_percentage is None:
        return "new"
    delta = current_percentage - previous_percentage
    if delta >= Decimal("5"):
        return "improving"
    if delta <= Decimal("-5"):
        return "declining"
    return "stable"


def _attendance_percentage(assessment: Assessment, student: StudentProfile) -> Decimal | None:
    qs = AttendanceEntry.objects.filter(
        student=student,
        session__offering__term=assessment.offering.term,
    )
    total = qs.count()
    if not total:
        return None
    present = qs.filter(status__in=(AttendanceEntry.PRESENT, AttendanceEntry.LATE, AttendanceEntry.EXCUSED)).count()
    return (Decimal(present) / Decimal(total) * Decimal("100")).quantize(Decimal("0.01"))


def _discipline_incident_count(assessment: Assessment, student: StudentProfile) -> int:
    qs = Incident.objects.filter(student=student)
    term = assessment.offering.term
    if term.start_date and term.end_date:
        qs = qs.filter(incident_date__range=(term.start_date, term.end_date))
    return qs.exclude(status=Incident.DISMISSED).count()


def _comment_parts(
    *,
    student: StudentProfile,
    course_name: str,
    current_percentage: Decimal | None,
    band: str,
    trend: str,
    attendance: Decimal | None,
    incidents: int,
) -> tuple[str, list[str], list[str], list[str]]:
    name = _student_name(student)
    strengths: list[str] = []
    weak_areas: list[str] = []
    recommendations: list[str] = []

    if current_percentage is None:
        opening = f"{name} is yet to receive a recorded score in {course_name}."
        recommendations.append("Record the assessment score, then review the generated comment again.")
    elif band == "excellent":
        opening = f"{name} has demonstrated excellent achievement in {course_name}, scoring {current_percentage}%."
        strengths.append(f"Excellent command of {course_name} concepts")
        recommendations.append("Provide enrichment tasks to keep stretching this strong performance.")
    elif band == "strong":
        opening = f"{name} has produced a strong performance in {course_name}, scoring {current_percentage}%."
        strengths.append(f"Strong understanding in {course_name}")
        recommendations.append("Encourage continued practice to move from strong to excellent achievement.")
    elif band == "good":
        opening = f"{name} has made good progress in {course_name}, scoring {current_percentage}%."
        strengths.append(f"Secure foundational progress in {course_name}")
        recommendations.append("Target the weaker question areas through guided revision.")
    elif band == "developing":
        opening = f"{name} is developing steadily in {course_name}, scoring {current_percentage}%."
        weak_areas.append(f"Needs firmer mastery in {course_name}")
        recommendations.append("Schedule short, regular practice tasks and check understanding after each topic.")
    else:
        opening = f"{name} needs focused support in {course_name}, scoring {current_percentage}%."
        weak_areas.append(f"Below expected performance in {course_name}")
        recommendations.append("Arrange remedial support, parent follow-up and weekly progress checks.")

    if trend == "improving":
        strengths.append("Improving performance trend")
        trend_sentence = "The improvement trend is encouraging and should be reinforced with consistent study habits."
    elif trend == "declining":
        weak_areas.append("Recent performance decline")
        trend_sentence = "Recent performance has declined, so timely support and revision planning are recommended."
    elif trend == "stable":
        trend_sentence = "Performance is stable, and the next goal is to build stronger consistency and confidence."
    elif trend == "new":
        trend_sentence = "This result gives a useful baseline for future progress tracking."
    else:
        trend_sentence = "A score is needed before a fuller academic trend can be assessed."

    conduct_sentence = "Conduct records show no major concerns for this period."
    if incidents:
        weak_areas.append("Conduct follow-up required")
        recommendations.append("Use clear behaviour targets alongside academic support.")
        conduct_sentence = f"There {'is' if incidents == 1 else 'are'} {incidents} conduct record{'s' if incidents != 1 else ''} to follow up."

    attendance_sentence = ""
    if attendance is not None:
        if attendance >= 90:
            strengths.append("Strong attendance")
            attendance_sentence = f"Attendance is strong at {attendance}%."
        elif attendance >= 75:
            attendance_sentence = f"Attendance is acceptable at {attendance}%, with room for further consistency."
        else:
            weak_areas.append("Attendance needs improvement")
            recommendations.append("Improve attendance consistency to support classroom progress.")
            attendance_sentence = f"Attendance is low at {attendance}% and may affect learning progress."

    comment = " ".join(part for part in [opening, trend_sentence, attendance_sentence, conduct_sentence] if part)
    return comment, strengths, weak_areas, recommendations


def build_report_comment_suggestion(assessment: Assessment, score: AssessmentScore | None, student: StudentProfile) -> ReportCommentSuggestion:
    current_percentage = percentage(score.score, assessment.max_score) if score else None
    band = _band(current_percentage)
    trend = _trend(assessment, student, current_percentage)
    attendance = _attendance_percentage(assessment, student)
    incidents = _discipline_incident_count(assessment, student)
    course_name = assessment.offering.course.name
    comment, strengths, weak_areas, recommendations = _comment_parts(
        student=student,
        course_name=course_name,
        current_percentage=current_percentage,
        band=band,
        trend=trend,
        attendance=attendance,
        incidents=incidents,
    )
    return ReportCommentSuggestion(
        student=student,
        comment=comment,
        performance_band=band,
        trend=trend,
        attendance_percentage=attendance,
        discipline_incidents=incidents,
        strengths=strengths,
        weak_areas=weak_areas,
        recommendations=recommendations,
    )


def persist_term_comment_suggestion(assessment: Assessment, suggestion: ReportCommentSuggestion):
    term = assessment.offering.term
    return ReportCardCommentSuggestion.objects.update_or_create(
        student=suggestion.student,
        term=term,
        defaults={
            "comment": suggestion.comment,
            "strengths": suggestion.strengths,
            "weak_areas": suggestion.weak_areas,
            "recommendations": suggestion.recommendations,
        },
    )[0]
