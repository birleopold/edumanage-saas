from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from django.db import connection
from django.utils import timezone

try:  # django-tenants is available in SaaS/PostgreSQL mode.
    from django_tenants.utils import tenant_context
except Exception:  # pragma: no cover - local SQLite fallback
    tenant_context = None


DEFAULT_FEATURE_FLAGS: tuple[tuple[str, bool], ...] = (
    ("academics", True),
    ("admissions", True),
    ("attendance", True),
    ("assessments", True),
    ("announcements", True),
    ("coursework", True),
    ("students", True),
    ("teachers", True),
    ("parents", True),
    ("finance", True),
    ("library", True),
    ("transport", True),
    ("hostels", True),
    ("inventory", True),
    ("documents", True),
    ("timetable", True),
    ("exams", True),
    ("reports", True),
    ("messaging", True),
    ("hr", True),
    ("analytics", True),
    ("audit", True),
)


@dataclass(frozen=True)
class TenantOnboardingResult:
    tenant: object
    domain: object
    organization: object
    campus: object
    admin_user: object
    setup_token: object | None
    academic_year: object
    academic_term: object
    feature_flags_created: int
    feature_flags_total: int
    login_domain: str
    tenant_schema_used: bool


@contextmanager
def tenant_data_context(tenant):
    """Write school records into the tenant schema when PostgreSQL tenancy is active.

    Local development uses SQLite without PostgreSQL schemas, so the same function
    also works as a no-op context manager for the preview database.
    """
    if connection.vendor == "postgresql" and tenant_context is not None:
        with tenant_context(tenant):
            yield True
    else:
        yield False


def _current_academic_year_dates(today: date) -> tuple[str, date, date]:
    return str(today.year), date(today.year, 1, 1), date(today.year, 12, 31)


def _seed_roles():
    from apps.tenant.users.models import Role

    roles = {}
    for code, label in Role.CODE_CHOICES:
        role, _created = Role.objects.get_or_create(code=code, defaults={"name": label})
        if role.name != label:
            role.name = label
            role.save(update_fields=["name"])
        roles[code] = role
    return roles


def _seed_owner_user(*, email: str, username: str, first_name: str = "", last_name: str = ""):
    from apps.tenant.users.models import PasswordSetupToken, Role, User, UserRole

    roles = _seed_roles()
    admin_role = roles[Role.ADMIN]

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_staff": True,
            "is_active": True,
            "must_change_password": True,
        },
    )

    changed_fields = []
    for field, value in {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "is_staff": True,
        "is_active": True,
        "must_change_password": True,
    }.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed_fields.append(field)

    if created:
        user.set_unusable_password()
        changed_fields.append("password")

    if changed_fields:
        user.save(update_fields=changed_fields)

    UserRole.objects.get_or_create(user=user, role=admin_role, campus=None)
    setup_token = PasswordSetupToken.create_for_user(user)
    return user, setup_token


def _seed_feature_flags() -> tuple[int, int]:
    from apps.tenant.orgsettings.models import FeatureFlag

    created_count = 0
    for code, enabled in DEFAULT_FEATURE_FLAGS:
        _flag, created = FeatureFlag.objects.get_or_create(
            code=code,
            campus=None,
            defaults={"is_enabled": enabled},
        )
        if created:
            created_count += 1
    return created_count, len(DEFAULT_FEATURE_FLAGS)


def _seed_current_academic_period():
    from apps.tenant.academics.models import AcademicTerm, AcademicYear

    today = timezone.localdate()
    year_name, start_date, end_date = _current_academic_year_dates(today)

    AcademicYear.objects.filter(is_current=True).exclude(name=year_name).update(is_current=False)
    academic_year, _created = AcademicYear.objects.get_or_create(
        name=year_name,
        defaults={
            "start_date": start_date,
            "end_date": end_date,
            "is_current": True,
        },
    )
    year_updates = []
    for field, value in {"start_date": start_date, "end_date": end_date, "is_current": True}.items():
        if getattr(academic_year, field) != value:
            setattr(academic_year, field, value)
            year_updates.append(field)
    if year_updates:
        academic_year.save(update_fields=year_updates)

    AcademicTerm.objects.filter(is_current=True).exclude(year=academic_year, name="Term 1").update(is_current=False)
    academic_term, _created = AcademicTerm.objects.get_or_create(
        year=academic_year,
        name="Term 1",
        defaults={
            "type": AcademicTerm.TERM,
            "order": 1,
            "start_date": today,
            "is_current": True,
        },
    )
    term_updates = []
    for field, value in {"type": AcademicTerm.TERM, "order": 1, "is_current": True}.items():
        if getattr(academic_term, field) != value:
            setattr(academic_term, field, value)
            term_updates.append(field)
    if term_updates:
        academic_term.save(update_fields=term_updates)

    return academic_year, academic_term


def provision_school_tenant(
    *,
    tenant,
    domain,
    owner_email: str,
    owner_username: str,
    owner_first_name: str = "",
    owner_last_name: str = "",
    organization_email: str = "",
    organization_phone: str = "",
    organization_address: str = "",
) -> TenantOnboardingResult:
    """Create all tenant-side defaults for a newly added school/client."""
    with tenant_data_context(tenant) as tenant_schema_used:
        # Import inside the schema context so tenant-aware managers point at the
        # correct schema in PostgreSQL mode.
        from apps.tenant.orgsettings.models import Campus, OrganizationProfile

        profile = OrganizationProfile.objects.filter(tenant_schema_name=tenant.schema_name).order_by("id").first()
        if profile is None:
            profile = OrganizationProfile.objects.filter(name=tenant.name).order_by("id").first()

        profile_defaults = {
            "legal_name": tenant.name,
            "tenant_schema_name": tenant.schema_name,
            "tenant_domain": domain.domain,
            "tenant_status": tenant.status,
            "email": organization_email or owner_email,
            "phone": organization_phone,
            "address": organization_address,
        }
        if profile is None:
            profile = OrganizationProfile.objects.create(name=tenant.name, **profile_defaults)
        else:
            profile_updates = []
            if profile.name != tenant.name:
                profile.name = tenant.name
                profile_updates.append("name")
            for field, value in profile_defaults.items():
                if value and getattr(profile, field, None) != value:
                    setattr(profile, field, value)
                    profile_updates.append(field)
            if profile_updates:
                profile_updates.append("updated_at")
                profile.save(update_fields=profile_updates)

        campus, _created = Campus.objects.get_or_create(
            organization=profile,
            is_default=True,
            defaults={
                "name": "Main Campus",
                "code": "MAIN",
                "email": organization_email or owner_email,
                "phone": organization_phone,
                "address": organization_address,
                "is_active": True,
            },
        )
        campus_updates = []
        for field, value in {
            "name": "Main Campus",
            "code": campus.code or "MAIN",
            "email": organization_email or owner_email,
            "phone": organization_phone,
            "address": organization_address,
            "is_active": True,
            "is_default": True,
        }.items():
            if value and getattr(campus, field, None) != value:
                setattr(campus, field, value)
                campus_updates.append(field)
        if campus_updates:
            campus.save(update_fields=campus_updates)

        admin_user, setup_token = _seed_owner_user(
            email=owner_email,
            username=owner_username,
            first_name=owner_first_name,
            last_name=owner_last_name,
        )
        feature_flags_created, feature_flags_total = _seed_feature_flags()
        academic_year, academic_term = _seed_current_academic_period()

    return TenantOnboardingResult(
        tenant=tenant,
        domain=domain,
        organization=profile,
        campus=campus,
        admin_user=admin_user,
        setup_token=setup_token,
        academic_year=academic_year,
        academic_term=academic_term,
        feature_flags_created=feature_flags_created,
        feature_flags_total=feature_flags_total,
        login_domain=domain.domain,
        tenant_schema_used=tenant_schema_used,
    )
