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
    if not _is_campus_admin(user) or _is_global_admin(user):
        return None
    from apps.tenant.users.models import UserRole
    assignment = UserRole.objects.filter(user=user, role__code=Role.CAMPUS_ADMIN, campus__isnull=False).select_related("campus").first()
    return assignment.campus if assignment else None

def user_can_access_campus(user, campus: Optional[Campus]) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if _is_global_admin(user):
        return True
    if not _is_campus_admin(user) or campus is None:
        return False
    user_campus = get_user_campus_scope(user)
    return bool(user_campus and user_campus.pk == campus.pk)

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
    user_campus = get_user_campus_scope(user)
    if not user_campus:
        return queryset.none()
    return queryset.filter(**{campus_field: user_campus})

def get_accessible_campuses(user):
    from apps.tenant.orgsettings.services import get_or_create_organization
    if _is_global_admin(user):
        organization = get_or_create_organization()
        return Campus.objects.filter(organization=organization, is_active=True)
    user_campus = get_user_campus_scope(user)
    if user_campus:
        return Campus.objects.filter(pk=user_campus.pk, is_active=True)
    return Campus.objects.none()

def validate_campus_access(user, campus_id: Optional[int]) -> bool:
    if campus_id is None:
        return _is_global_admin(user)
    try:
        campus = Campus.objects.get(pk=campus_id, is_active=True)
    except Campus.DoesNotExist:
        return False
    return user_can_access_campus(user, campus)
