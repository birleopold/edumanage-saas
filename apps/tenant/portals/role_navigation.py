"""Single source of truth for portal role routing and shell selection."""

from __future__ import annotations

from collections.abc import Iterable

from django.urls import reverse

from apps.tenant.users.models import Role


ADMIN_PORTAL_ROLE_CODES = (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)
GLOBAL_ADMIN_ROLE_CODES = (Role.ADMIN, Role.PRINCIPAL)


def role_codes_for(user) -> set[str]:
    """Read a user's role codes once, using prefetched values when available."""

    if not getattr(user, "is_authenticated", False):
        return set()

    prefetched = getattr(user, "_prefetched_objects_cache", {}).get("roles")
    if prefetched is not None:
        return {role.code for role in prefetched}

    roles = getattr(user, "roles", None)
    if roles is None:
        return set()
    return set(roles.values_list("code", flat=True))


def has_any_role(user, role_codes: Iterable[str], *, known_codes: set[str] | None = None) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    codes = known_codes if known_codes is not None else role_codes_for(user)
    return bool(codes.intersection(set(role_codes)))


def is_admin_portal_user(user, *, known_codes: set[str] | None = None) -> bool:
    return has_any_role(user, ADMIN_PORTAL_ROLE_CODES, known_codes=known_codes)


def is_global_admin_user(user, *, known_codes: set[str] | None = None) -> bool:
    return has_any_role(user, GLOBAL_ADMIN_ROLE_CODES, known_codes=known_codes)


def portal_base_template_for(user) -> str:
    codes = role_codes_for(user)
    if is_admin_portal_user(user, known_codes=codes):
        return "portals/admin/base.html"
    if Role.TEACHER in codes:
        return "portals/teacher/base.html"
    if Role.STUDENT in codes:
        return "portals/student/base.html"
    if Role.PARENT in codes:
        return "portals/parent/base.html"
    # Preserve the existing neutral fallback for accounts awaiting role setup.
    return "portals/admin/base.html"


def portal_home_name_for(user) -> str:
    codes = role_codes_for(user)
    if is_admin_portal_user(user, known_codes=codes):
        return "admin_home"
    if Role.TEACHER in codes:
        return "teacher_home"
    if Role.STUDENT in codes:
        return "student_home"
    if Role.PARENT in codes:
        return "parent_home"
    return "user_profile"


def portal_home_url_for(user) -> str:
    return reverse(portal_home_name_for(user))
