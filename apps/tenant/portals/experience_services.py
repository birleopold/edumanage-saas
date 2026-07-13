"""Shared helpers for portal UX (setup checklist, onboarding)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from decouple import config
from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.tenant.academics.models import AcademicTerm, AcademicYear, ClassGroup, Course
from apps.tenant.audit.models import BackupJob
from apps.tenant.finance.integration_models import IntegrationProviderConfig
from apps.tenant.finance.models import FeeItem, MobilePaymentRequest, OutboundMessageLog, PaymentGatewayEvent
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.models import WebPushSubscription
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role, User, UserRole


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


def _health_status(score: int, weight: int) -> str:
    if score >= weight:
        return "complete"
    if score > 0:
        return "partial"
    return "missing"


def _health_item(
    *,
    key: str,
    title: str,
    description: str,
    score: int,
    weight: int,
    url_name: str | None,
    cta: str,
    icon: str,
    evidence: list[str],
    next_step: str,
) -> dict[str, Any]:
    score = max(0, min(score, weight))
    return {
        "key": key,
        "title": title,
        "description": description,
        "score": score,
        "weight": weight,
        "percent": round((score / weight) * 100) if weight else 100,
        "status": _health_status(score, weight),
        "gap_points": max(0, weight - score),
        "url": _safe_url(url_name) if url_name else None,
        "cta": cta,
        "icon": icon,
        "evidence": evidence,
        "next_step": next_step,
    }


def _runtime_setting(name: str, default: str = "") -> str:
    value = getattr(settings, name, None)
    if value:
        return value
    return config(name, default=default)


def _configured_payment_provider_count() -> int:
    provider_types = (IntegrationProviderConfig.MTN_MOMO, IntegrationProviderConfig.AIRTEL_MONEY)
    configured_rows = IntegrationProviderConfig.objects.filter(
        provider_type__in=provider_types,
        is_active=True,
    ).count()
    env_configured = sum(
        1
        for prefix in ("MTN_MOMO", "AIRTEL_MONEY")
        if _runtime_setting(f"{prefix}_COLLECTION_URL")
        and (
            _runtime_setting(f"{prefix}_COLLECTION_TOKEN")
            or _runtime_setting(f"{prefix}_SUBSCRIPTION_KEY")
        )
    )
    return max(configured_rows, env_configured)


def build_school_health_score() -> dict[str, Any]:
    """Weighted readiness score for operational school setup."""
    org = get_or_create_organization()
    now = timezone.now()

    active_campuses = Campus.objects.filter(organization=org, is_active=True) if org else Campus.objects.none()
    campus_count = active_campuses.count()
    default_campus = active_campuses.filter(is_default=True).exists()

    current_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = AcademicTerm.objects.filter(is_current=True).first()
    any_term_count = AcademicTerm.objects.count()

    fee_count = FeeItem.objects.filter(is_active=True).count()
    inactive_fee_count = FeeItem.objects.filter(is_active=False).count()

    required_roles = {Role.ADMIN, Role.CAMPUS_ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT}
    existing_roles = set(Role.objects.filter(code__in=required_roles).values_list("code", flat=True))
    assigned_role_count = UserRole.objects.filter(role__code__in=required_roles, user__is_active=True).count()
    admin_assigned = UserRole.objects.filter(role__code=Role.ADMIN, user__is_active=True).exists()

    pwa_public_key = bool(_runtime_setting("WEB_PUSH_PUBLIC_KEY"))
    pwa_private_key = bool(_runtime_setting("WEB_PUSH_PRIVATE_KEY"))
    active_push_subscriptions = WebPushSubscription.objects.filter(is_active=True).count()

    latest_backup = BackupJob.objects.order_by("-created_at").first()
    recent_success = BackupJob.objects.filter(
        status__in=(BackupJob.SUCCESS, BackupJob.RESTORE_TESTED),
        created_at__gte=now - timedelta(days=14),
    ).exists()
    any_backup = latest_backup is not None

    payment_provider_count = _configured_payment_provider_count()
    payment_activity = PaymentGatewayEvent.objects.exists() or MobilePaymentRequest.objects.exists()

    items = [
        _health_item(
            key="campuses",
            title="Campuses configured",
            description="Active campuses let student records, staff scope and reporting use the right school location.",
            score=15 if campus_count and default_campus else 10 if campus_count else 0,
            weight=15,
            url_name="admin_orgsettings_campuses",
            cta="Manage campuses",
            icon="ph-buildings",
            evidence=[
                f"{campus_count} active campus{'es' if campus_count != 1 else ''}",
                "Default campus set" if default_campus else "No default campus selected",
            ],
            next_step="Add at least one active campus and mark the main campus as default.",
        ),
        _health_item(
            key="terms",
            title="Academic terms active",
            description="A current year and term are required for attendance, fees, coursework, exams and reports.",
            score=15 if current_year and current_term else 8 if any_term_count else 0,
            weight=15,
            url_name="admin_academic_term_list",
            cta="Manage terms",
            icon="ph-calendar-check",
            evidence=[
                f"Current year: {current_year.name}" if current_year else "No current academic year",
                f"Current term: {current_term}" if current_term else f"{any_term_count} term record{'s' if any_term_count != 1 else ''}",
            ],
            next_step="Create the school year and mark the live academic term as current.",
        ),
        _health_item(
            key="fees",
            title="Fee structures set",
            description="Active fee items are the base for invoices, balances, parent statements and payment reminders.",
            score=15 if fee_count else 5 if inactive_fee_count else 0,
            weight=15,
            url_name="admin_fee_items_list",
            cta="Configure fees",
            icon="ph-wallet",
            evidence=[
                f"{fee_count} active fee item{'s' if fee_count != 1 else ''}",
                f"{inactive_fee_count} inactive fee item{'s' if inactive_fee_count != 1 else ''}",
            ],
            next_step="Add tuition and required charge items before generating invoices.",
        ),
        _health_item(
            key="roles",
            title="Roles assigned",
            description="Role records and user assignments keep admin, campus, teacher, student and parent access predictable.",
            score=15 if required_roles.issubset(existing_roles) and admin_assigned and assigned_role_count >= 2 else 8 if existing_roles or assigned_role_count else 0,
            weight=15,
            url_name="admin_users_list",
            cta="Manage users",
            icon="ph-user-gear",
            evidence=[
                f"{len(existing_roles)} of {len(required_roles)} core role records",
                f"{assigned_role_count} active user role assignment{'s' if assigned_role_count != 1 else ''}",
                "Admin role assigned" if admin_assigned else "No active admin role assignment",
            ],
            next_step="Seed core roles and assign at least one admin plus operational staff roles.",
        ),
        _health_item(
            key="pwa",
            title="PWA alerts ready",
            description="Push keys and active subscriptions allow browser alerts for reminders, digests and school updates.",
            score=15 if pwa_public_key and pwa_private_key else 8 if pwa_public_key or active_push_subscriptions else 0,
            weight=15,
            url_name="admin_user_devices",
            cta="Open device monitor",
            icon="ph-device-mobile",
            evidence=[
                "Public VAPID key set" if pwa_public_key else "Public VAPID key missing",
                "Private VAPID key set" if pwa_private_key else "Private VAPID key missing",
                f"{active_push_subscriptions} active push subscription{'s' if active_push_subscriptions != 1 else ''}",
            ],
            next_step="Generate VAPID keys and have staff or parents subscribe from their browser.",
        ),
        _health_item(
            key="backups",
            title="Backups enabled",
            description="Recent backup jobs prove the school can recover data if an operational or hosting problem occurs.",
            score=10 if recent_success else 5 if any_backup else 0,
            weight=10,
            url_name="audit_backup_jobs",
            cta="Review backups",
            icon="ph-database",
            evidence=[
                f"Latest backup: {latest_backup.get_status_display()}" if latest_backup else "No backup jobs recorded",
                "Recent successful backup found" if recent_success else "No successful backup in the last 14 days",
            ],
            next_step="Request a backup and confirm at least one recent successful or restore-tested job.",
        ),
        _health_item(
            key="payments",
            title="Payment connectors configured",
            description="Mobile money provider setup lets parents initiate payments and finance teams reconcile gateway callbacks.",
            score=15 if payment_provider_count else 8 if payment_activity else 0,
            weight=15,
            url_name="admin_connectors_home",
            cta="Open integrations",
            icon="ph-plugs-connected",
            evidence=[
                f"{payment_provider_count} active payment provider configuration{'s' if payment_provider_count != 1 else ''}",
                "Gateway activity found" if payment_activity else "No payment gateway activity yet",
            ],
            next_step="Configure MTN MoMo or Airtel Money in Integrations, then test a collection flow.",
        ),
    ]
    total = sum(item["score"] for item in items)
    possible = sum(item["weight"] for item in items)
    percent = round((total / possible) * 100) if possible else 100
    if percent >= 85:
        level = "Ready"
        tone = "green"
    elif percent >= 60:
        level = "Nearly ready"
        tone = "amber"
    else:
        level = "Needs setup"
        tone = "red"

    return {
        "items": items,
        "score": total,
        "possible": possible,
        "percent": percent,
        "level": level,
        "tone": tone,
        "complete_count": sum(1 for item in items if item["status"] == "complete"),
        "partial_count": sum(1 for item in items if item["status"] == "partial"),
        "missing_count": sum(1 for item in items if item["status"] == "missing"),
        "top_gaps": sorted(
            [item for item in items if item["status"] != "complete"],
            key=lambda item: (-item["gap_points"], item["title"]),
        )[:3],
    }


def messaging_activity_summary(days: int = 30):
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
