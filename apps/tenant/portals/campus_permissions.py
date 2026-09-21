"""Campus-level permission utilities that fail closed by default."""
from functools import wraps
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from apps.tenant.orgsettings.models import Campus
from apps.tenant.users.models import Role

from .role_navigation import is_global_admin_user

def _is_global_admin(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and is_global_admin_user(user))

def _is_campus_admin(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.has_role(Role.CAMPUS_ADMIN))

def get_user_campus_scope(user) -> Optional[Campus]:
    """Return the legacy primary campus for single-campus workflows."""
    return get_user_campus_scopes(user).first()


def get_user_campus_scopes(user):
    """Return every active campus explicitly assigned to a campus administrator."""
    if not _is_campus_admin(user) or _is_global_admin(user):
        return Campus.objects.none()
    from apps.tenant.users.models import UserRole

    campus_ids = UserRole.objects.filter(
        user=user,
        role__code=Role.CAMPUS_ADMIN,
        campus__isnull=False,
        campus__is_active=True,
    ).values_list("campus_id", flat=True)
    return Campus.objects.filter(pk__in=campus_ids, is_active=True).order_by("name", "pk")

def user_can_access_campus(user, campus: Optional[Campus]) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if _is_global_admin(user):
        return True
    if not _is_campus_admin(user) or campus is None:
        return False
    return get_user_campus_scopes(user).filter(pk=campus.pk).exists()

def campus_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if _is_global_admin(request.user):
            return view_func(request, *args, **kwargs)
        if _is_campus_admin(request.user) and get_user_campus_scope(request.user) is not None:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("A valid admin campus assignment is required.")
    return wrapper

def enforce_campus_scope(queryset, user, campus_field="campus"):
    if _is_global_admin(user):
        return queryset
    user_campuses = get_user_campus_scopes(user)
    if not user_campuses.exists():
        return queryset.none()
    return queryset.filter(**{f"{campus_field}__in": user_campuses})

def get_accessible_campuses(user):
    from apps.tenant.orgsettings.services import get_or_create_organization
    if _is_global_admin(user):
        organization = get_or_create_organization()
        return Campus.objects.filter(organization=organization, is_active=True)
    return get_user_campus_scopes(user)

def validate_campus_access(user, campus_id: Optional[int]) -> bool:
    if campus_id is None:
        return _is_global_admin(user)
    try:
        campus = Campus.objects.get(pk=campus_id, is_active=True)
    except Campus.DoesNotExist:
        return False
    return user_can_access_campus(user, campus)
