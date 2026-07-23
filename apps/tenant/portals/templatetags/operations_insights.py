from __future__ import annotations

from django import template
from django.db.models import Q
from django.utils import timezone

from apps.tenant.announcements.models import Announcement
from apps.tenant.exams.models import Exam, ExamPaper
from apps.tenant.library.models import Book, BookCopy, BookLoan, Fine, Reservation
from apps.tenant.parents.models import ParentProfile
from apps.tenant.portals.campus_permissions import get_user_campus_scope


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

    return {
        "periods": exams.count(),
        "active": exams.filter(is_active=True).count(),
        "digital": exams.filter(exam_mode__in=[Exam.ONLINE, Exam.HYBRID]).count(),
        "papers": papers.count(),
        "published": papers.filter(results_published=True).count(),
    }
