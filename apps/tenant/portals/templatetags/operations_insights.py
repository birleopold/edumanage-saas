from __future__ import annotations

from django import template
from django.db.models import Q, Sum
from django.utils import timezone

from apps.tenant.announcements.models import Announcement
from apps.tenant.discipline.models import Incident
from apps.tenant.documents.models import Document
from apps.tenant.exams.models import Exam, ExamPaper
from apps.tenant.hr.models import Department, Position, StaffProfile
from apps.tenant.library.models import Book, BookCopy, BookLoan, Fine, Reservation
from apps.tenant.parents.models import ParentProfile
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.sickbay.models import SickbayVisit, StudentMedicalProfile
from apps.tenant.transport.models import Driver, StudentTransportAssignment, TransportRoute, Vehicle


register = template.Library()


def _campus_scope(request):
    if request is None or not getattr(request, "user", None):
        return None
    try:
        return get_user_campus_scope(request.user)
    except Exception:
        return None


@register.simple_tag(takes_context=True)
def parent_registry_summary(context):
    request = context.get("request")
    queryset = ParentProfile.objects.all()
    campus = _campus_scope(request)
    if campus is not None:
        queryset = queryset.filter(
            Q(parentstudentlink__student__campus=campus)
            | Q(parentstudentlink__isnull=True)
        ).distinct()

    return {
        "total": queryset.count(),
        "active": queryset.filter(is_active=True).count(),
        "portal": queryset.filter(user__isnull=False).count(),
        "unlinked": queryset.filter(parentstudentlink__isnull=True).count(),
        "digest": queryset.filter(digest_enabled=True).count(),
    }


@register.simple_tag
def announcement_workspace_summary():
    queryset = Announcement.objects.all()
    return {
        "total": queryset.count(),
        "active": queryset.filter(is_active=True).count(),
        "urgent": queryset.filter(is_urgent=True, is_active=True).count(),
        "parent_ready": queryset.filter(
            is_urgent=True,
            is_active=True,
            audience__in=[Announcement.ALL, Announcement.PARENTS],
        ).count(),
    }


@register.simple_tag(takes_context=True)
def library_workspace_summary(context):
    request = context.get("request")
    campus = _campus_scope(request)
    loans = BookLoan.objects.all()
    fines = Fine.objects.all()
    reservations = Reservation.objects.all()

    if campus is not None:
        borrower_scope = Q(student__campus=campus) | Q(staff__campus=campus)
        loans = loans.filter(borrower_scope)
        fines = fines.filter(borrower_scope)
        reservations = reservations.filter(borrower_scope)

    today = timezone.localdate()
    return {
        "titles": Book.objects.filter(is_active=True).count(),
        "copies": BookCopy.objects.filter(is_active=True).count(),
        "available": BookCopy.objects.filter(is_active=True, status=BookCopy.AVAILABLE).count(),
        "open_loans": loans.exclude(status=BookLoan.RETURNED).count(),
        "overdue": loans.exclude(status=BookLoan.RETURNED).filter(due_date__lt=today).count(),
        "reservations": reservations.filter(status=Reservation.PENDING).count(),
        "unpaid_fines": fines.filter(status=Fine.UNPAID).count(),
    }


@register.simple_tag(takes_context=True)
def exam_workspace_summary(context):
    request = context.get("request")
    campus = _campus_scope(request)
    papers = ExamPaper.objects.all()
    if campus is not None:
        papers = papers.filter(offering__campus=campus)
        exam_ids = papers.values_list("exam_id", flat=True)
        exams = Exam.objects.filter(pk__in=exam_ids).distinct()
    else:
        exams = Exam.objects.all()

    paper_count = papers.count()
    published_count = papers.filter(results_published=True).count()
    return {
        "periods": exams.count(),
        "active": exams.filter(is_active=True).count(),
        "digital": exams.filter(exam_mode__in=[Exam.ONLINE, Exam.HYBRID]).count(),
        "papers": paper_count,
        "published": published_count,
        "unpublished": max(0, paper_count - published_count),
    }


@register.simple_tag(takes_context=True)
def discipline_workspace_summary(context):
    request = context.get("request")
    queryset = Incident.objects.all()
    campus = _campus_scope(request)
    if campus is not None:
        queryset = queryset.filter(student__campus=campus)

    return {
        "total": queryset.count(),
        "open": queryset.filter(status=Incident.OPEN).count(),
        "high": queryset.filter(status=Incident.OPEN, severity=Incident.HIGH).count(),
        "resolved": queryset.filter(status=Incident.RESOLVED).count(),
        "dismissed": queryset.filter(status=Incident.DISMISSED).count(),
    }


@register.simple_tag(takes_context=True)
def sickbay_workspace_summary(context):
    request = context.get("request")
    visits = SickbayVisit.objects.all()
    profiles = StudentMedicalProfile.objects.all()
    campus = _campus_scope(request)
    if campus is not None:
        visits = visits.filter(campus=campus)
        profiles = profiles.filter(student__campus=campus)

    today = timezone.localdate()
    today_visits = visits.filter(visit_at__date=today)
    return {
        "total": visits.count(),
        "today": today_visits.count(),
        "severe_today": today_visits.filter(severity=SickbayVisit.SEVERE).count(),
        "notified_today": today_visits.filter(parent_notified=True).count(),
        "follow_up": visits.filter(follow_up_required=True).count(),
        "escalated": visits.filter(outcome__in=[SickbayVisit.REFERRED, SickbayVisit.EMERGENCY]).count(),
        "profiles": profiles.count(),
        "alerts": profiles.filter(
            Q(allergies__gt="")
            | Q(chronic_conditions__gt="")
            | Q(current_medication__gt="")
        ).count(),
    }


@register.filter
def sickbay_outcome_label(value):
    return dict(SickbayVisit.OUTCOME_CHOICES).get(value, value)


@register.simple_tag(takes_context=True)
def transport_workspace_summary(context):
    request = context.get("request")
    campus = _campus_scope(request)
    assignments = StudentTransportAssignment.objects.filter(is_active=True)
    if campus is not None:
        assignments = assignments.filter(student__campus=campus)

    vehicles = Vehicle.objects.all()
    today = timezone.localdate()
    return {
        "vehicles": vehicles.count(),
        "operational": vehicles.filter(status=Vehicle.OPERATIONAL, is_active=True).count(),
        "maintenance": vehicles.filter(status=Vehicle.MAINTENANCE).count(),
        "out_of_service": vehicles.filter(status=Vehicle.OUT_OF_SERVICE).count(),
        "maintenance_due": vehicles.filter(next_maintenance__isnull=False, next_maintenance__lte=today).count(),
        "gps_ready": vehicles.exclude(gps_device_id="").count(),
        "capacity": vehicles.filter(is_active=True).aggregate(total=Sum("capacity"))["total"] or 0,
        "routes": TransportRoute.objects.filter(is_active=True).count(),
        "drivers": Driver.objects.filter(is_active=True, status=Driver.ACTIVE).count(),
        "assignments": assignments.count(),
    }


@register.simple_tag
def document_workspace_summary():
    documents = Document.objects.all()
    return {
        "total": documents.count(),
        "active": documents.filter(is_active=True).count(),
        "all": documents.filter(audience=Document.ALL).count(),
        "teachers": documents.filter(audience=Document.TEACHERS).count(),
        "students": documents.filter(audience=Document.STUDENTS).count(),
        "parents": documents.filter(audience=Document.PARENTS).count(),
    }


@register.simple_tag(takes_context=True)
def hr_workspace_summary(context):
    request = context.get("request")
    campus = _campus_scope(request)
    staff = StaffProfile.objects.all()
    departments = Department.objects.all()
    positions = Position.objects.all()
    if campus is not None:
        staff = staff.filter(campus=campus)
        departments = departments.filter(Q(campus=campus) | Q(campus__isnull=True))
        positions = positions.filter(
            Q(department__campus=campus)
            | Q(department__campus__isnull=True)
            | Q(department__isnull=True)
        )

    return {
        "total": staff.count(),
        "active": staff.filter(is_active=True).count(),
        "teaching": staff.filter(staff_category=StaffProfile.TEACHING).count(),
        "non_teaching": staff.filter(staff_category=StaffProfile.NON_TEACHING).count(),
        "portal": staff.filter(user__isnull=False).count(),
        "departments": departments.filter(is_active=True).count(),
        "positions": positions.filter(is_active=True).count(),
        "attention": staff.filter(
            Q(department__isnull=True)
            | Q(position__isnull=True)
            | Q(email="")
            | Q(phone="")
        ).distinct().count(),
    }
