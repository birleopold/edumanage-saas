from __future__ import annotations

from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .engagement_models import ActivityCertificate, ActivityIncident
from .models import ActivityMember
from .programme_models import ActivityAchievement, ActivityAttendance


def learner_activity_summary(student):
    memberships = list(
        ActivityMember.objects.filter(student=student, is_active=True)
        .select_related("activity", "participation_profile", "participation_profile__group")
        .prefetch_related("achievements", "session_attendance__session")
        .order_by("activity__name")
    )
    rows = []
    total_sessions = 0
    attended_sessions = 0
    achievement_count = 0
    for membership in memberships:
        attendance = list(membership.session_attendance.select_related("session"))
        present = sum(
            1
            for item in attendance
            if item.status in {ActivityAttendance.PRESENT, ActivityAttendance.LATE, ActivityAttendance.ON_DUTY}
        )
        total = len(attendance)
        achievements = list(membership.achievements.all())
        total_sessions += total
        attended_sessions += present
        achievement_count += len(achievements)
        rows.append(
            {
                "membership": membership,
                "activity": membership.activity,
                "participation": getattr(membership, "participation_profile", None),
                "session_count": total,
                "attended_count": present,
                "attendance_rate": round((present / total) * 100, 1) if total else None,
                "achievements": achievements,
            }
        )
    incidents = ActivityIncident.objects.filter(student=student).select_related(
        "activity",
        "session",
    )
    visible_incidents = incidents.filter(confidential=False)
    open_incidents = incidents.exclude(
        status__in=(ActivityIncident.RESOLVED, ActivityIncident.CLOSED)
    ).count()
    attendance_rate = (
        round((attended_sessions / total_sessions) * 100, 1)
        if total_sessions
        else None
    )
    report_comment = build_activity_report_comment(
        membership_count=len(memberships),
        attendance_rate=attendance_rate,
        achievement_count=achievement_count,
        open_incident_count=open_incidents,
    )
    return {
        "student": student,
        "rows": rows,
        "membership_count": len(memberships),
        "session_count": total_sessions,
        "attended_count": attended_sessions,
        "attendance_rate": attendance_rate,
        "achievement_count": achievement_count,
        "open_incident_count": open_incidents,
        "incidents": visible_incidents.order_by("-occurred_at")[:20],
        "report_comment": report_comment,
    }


def build_activity_report_comment(
    *,
    membership_count,
    attendance_rate,
    achievement_count,
    open_incident_count,
):
    if membership_count == 0:
        return "The learner has no active co-curricular participation record for this period."
    parts = [
        f"The learner participates in {membership_count} co-curricular programme"
        + ("s" if membership_count != 1 else "")
        + "."
    ]
    if attendance_rate is not None:
        if attendance_rate >= 85:
            parts.append("Participation attendance is excellent.")
        elif attendance_rate >= 70:
            parts.append("Participation attendance is satisfactory.")
        else:
            parts.append("Participation attendance needs improvement.")
    if achievement_count:
        parts.append(
            f"The learner has recorded {achievement_count} achievement"
            + ("s" if achievement_count != 1 else "")
            + "."
        )
    if open_incident_count:
        parts.append(
            "Authorised staff should follow up the outstanding activity concern"
            + ("s" if open_incident_count != 1 else "")
            + "."
        )
    return " ".join(parts)


@transaction.atomic
def issue_activity_certificate(achievement, *, issued_by=None):
    if not achievement.pk:
        raise ValidationError("Save the achievement before issuing a certificate.")
    reference = f"ACT-{achievement.membership.student_id}-{achievement.pk}"
    student = achievement.membership.student
    activity = achievement.membership.activity
    snapshot = {
        "achievement_id": achievement.pk,
        "student_id": student.pk,
        "student_number": student.student_id,
        "student_name": student.get_full_name(),
        "activity_id": activity.pk,
        "activity_name": activity.name,
        "achievement_type": achievement.achievement_type,
        "achievement_level": achievement.level,
        "achievement_title": achievement.title,
        "achieved_on": achievement.achieved_on.isoformat(),
        "position": achievement.position,
        "description": achievement.description,
    }
    certificate, _ = ActivityCertificate.objects.update_or_create(
        achievement=achievement,
        defaults={
            "reference": reference,
            "title": achievement.title,
            "statement": (
                f"This certifies that {student.get_full_name()} "
                f"earned {achievement.title} through {activity.name} "
                f"at {achievement.get_level_display()} level."
            ),
            "issued_by": issued_by,
            "snapshot": snapshot,
            "is_revoked": False,
            "revoked_at": None,
            "revoked_by": None,
            "revocation_reason": "",
        },
    )
    certificate.full_clean()
    certificate.save()
    return certificate


def _qr(data: str, size=30 * mm):
    widget = QrCodeWidget(data)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(
        size,
        size,
        transform=[size / width, 0, 0, size / height, 0, 0],
    )
    drawing.add(widget)
    return drawing


def certificate_pdf(certificate, verify_url):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CertificateTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=28,
        leading=34,
        textColor=colors.HexColor("#1e3a8a"),
    )
    centre = ParagraphStyle(
        "CertificateCentre",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        fontSize=14,
        leading=22,
    )
    snapshot = certificate.snapshot or {}
    story = [
        Spacer(1, 12 * mm),
        Paragraph("CERTIFICATE OF ACHIEVEMENT", title_style),
        Spacer(1, 10 * mm),
        Paragraph(certificate.statement, centre),
        Spacer(1, 8 * mm),
        Paragraph(
            f"<b>{snapshot.get('student_name', certificate.achievement.membership.student)}</b>",
            ParagraphStyle(
                "Recipient",
                parent=centre,
                fontSize=22,
                leading=28,
                textColor=colors.HexColor("#0f172a"),
            ),
        ),
        Spacer(1, 7 * mm),
        Paragraph(
            f"Activity: <b>{snapshot.get('activity_name', certificate.achievement.membership.activity)}</b><br/>"
            f"Level: {certificate.achievement.get_level_display()} &nbsp;&nbsp; "
            f"Date: {certificate.achievement.achieved_on:%d %B %Y}",
            centre,
        ),
        Spacer(1, 10 * mm),
        Table(
            [
                ["Reference", certificate.reference],
                ["Status", "VALID" if certificate.is_valid else "REVOKED"],
            ],
            colWidths=[35 * mm, 80 * mm],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Spacer(1, 5 * mm),
        _qr(verify_url),
        Paragraph("Scan to verify this certificate against the live institution record.", centre),
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer
