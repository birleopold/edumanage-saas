"""Shared helpers for portal UX (setup checklist, onboarding)."""

from __future__ import annotations

from typing import Any

from django.urls import NoReverseMatch, reverse

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course
from apps.tenant.finance.models import FeeItem, OutboundMessageLog
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import User


_CONTACT_FIELDS = ("email", "phone", "address", "legal_name", "logo")


def _safe_url(name: str) -> str | None:
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def _profile_ready(org) -> bool:
    if not org or not (org.name or "").strip():
        return False
    return any(bool(getattr(org, field, None)) for field in _CONTACT_FIELDS)


def _checklist_item(
    *,
    key: str,
    title: str,
    description: str,
    done: bool,
    url_name: str | None,
    cta: str,
    icon: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "done": done,
        "url": _safe_url(url_name) if url_name else None,
        "cta": cta,
        "icon": icon,
    }


def build_school_setup_checklist() -> list[dict[str, Any]]:
    """First-login setup checklist for newly onboarded school tenants."""
    org = get_or_create_organization()

    has_profile = _profile_ready(org)
    has_campus = Campus.objects.filter(organization=org, is_active=True).exists() if org else False
    has_year = AcademicYear.objects.filter(is_current=True).exists()
    has_term = AcademicTerm.objects.filter(is_current=True).exists()
    has_classes = ClassGroup.objects.filter(is_active=True).exists()
    has_courses = Course.objects.filter(is_active=True).exists()
    has_teachers = TeacherProfile.objects.filter(is_active=True).exists()
    has_students = StudentProfile.objects.filter(is_active=True).exists()
    has_fees = FeeItem.objects.filter(is_active=True).exists()
    has_invited_users = User.objects.filter(is_active=True).count() > 1

    return [
        _checklist_item(
            key="school_profile",
            title="Add school profile",
            description="Confirm the school name, legal name, contact details, logo and branding.",
            done=has_profile,
            url_name="admin_orgsettings_org",
            cta="Open school profile",
            icon="ph-identification-card",
        ),
        _checklist_item(
            key="campus",
            title="Add campus",
            description="Create or confirm the main campus that will hold learners, staff and fees.",
            done=has_campus,
            url_name="admin_orgsettings_campuses",
            cta="Manage campuses",
            icon="ph-buildings",
        ),
        _checklist_item(
            key="academic_year",
            title="Add academic year",
            description="Set the current academic year for classes, assessments, billing and reports.",
            done=has_year,
            url_name="admin_academic_year_list",
            cta="Manage academic years",
            icon="ph-calendar-blank",
        ),
        _checklist_item(
            key="term",
            title="Add term",
            description="Set the active term so attendance, results and fee records use the correct period.",
            done=has_term,
            url_name="admin_academic_term_list",
            cta="Manage terms",
            icon="ph-calendar-check",
        ),
        _checklist_item(
            key="classes",
            title="Add classes",
            description="Create class groups or levels such as S1, P5, Year 7 or Senior Four.",
            done=has_classes,
            url_name="admin_classgroup_create",
            cta="Add class",
            icon="ph-users-three",
        ),
        _checklist_item(
            key="subjects_courses",
            title="Add subjects/courses",
            description="Add the subjects or courses taught by the school.",
            done=has_courses,
            url_name="admin_course_create",
            cta="Add course",
            icon="ph-books",
        ),
        _checklist_item(
            key="teachers",
            title="Add teachers",
            description="Register teaching staff so they can be assigned classes, subjects and portal roles.",
            done=has_teachers,
            url_name="admin_teachers_create",
            cta="Add teacher",
            icon="ph-chalkboard-teacher",
        ),
        _checklist_item(
            key="students",
            title="Add students",
            description="Add learners or import them before attendance, fees and reports go live.",
            done=has_students,
            url_name="admin_students_create",
            cta="Add student",
            icon="ph-student",
        ),
        _checklist_item(
            key="fees",
            title="Configure fees",
            description="Set up fee items before creating invoices and payment records.",
            done=has_fees,
            url_name="admin_fee_items_list",
            cta="Configure fees",
            icon="ph-wallet",
        ),
        _checklist_item(
            key="invite_users",
            title="Invite users",
            description="Create or invite additional admins, teachers, students or parent users.",
            done=has_invited_users,
            url_name="admin_users_list",
            cta="Manage users",
            icon="ph-user-plus",
        ),
    ]


def school_setup_progress() -> dict[str, Any]:
    items = build_school_setup_checklist()
    done = sum(1 for row in items if row.get("done"))
    total = len(items)
    return {
        "items": items,
        "done_count": done,
        "remaining_count": total - done,
        "total": total,
        "percent": round((done / total) * 100) if total else 100,
        "all_done": done == total,
    }


def messaging_activity_summary(days: int = 30):
    from django.utils import timezone
    from datetime import timedelta

    since = timezone.now() - timedelta(days=days)
    qs = OutboundMessageLog.objects.filter(created_at__gte=since)
    return {
        "since": since,
        "total": qs.count(),
        "sent": qs.filter(status=OutboundMessageLog.SENT).count(),
        "failed": qs.filter(status=OutboundMessageLog.FAILED).count(),
        "dry_run": qs.filter(status=OutboundMessageLog.DRY_RUN).count(),
        "no_phone": qs.filter(status=OutboundMessageLog.NO_PHONE).count(),
    }
