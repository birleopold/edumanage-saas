"""
Campus-level permission utilities and decorators.
"""
from functools import wraps
from typing import Optional

from django.http import HttpResponseForbidden

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.users.models import Role


def get_user_campus_scope(user) -> Optional[Campus]:
    """
    Get the campus scope for a campus admin user.
    Returns None if user is a global admin or not a campus admin.
    """
    if not user.is_authenticated:
        return None
    
    # Global admins have no campus restriction
    if user.has_role(Role.ADMIN):
        return None
    
    # Check if user is a campus admin
    from apps.tenant.users.models import UserRole
    campus_admin_role = UserRole.objects.filter(
        user=user,
        role__code=Role.CAMPUS_ADMIN,
        campus__isnull=False
    ).select_related('campus').first()
    
    if campus_admin_role:
        return campus_admin_role.campus
    
    return None


def user_can_access_campus(user, campus: Optional[Campus]) -> bool:
    """
    Check if user can access data for the given campus.
    
    - Global admins can access all campuses
    - Campus admins can only access their assigned campus
    - Other roles follow their natural scoping
    """
    if not user.is_authenticated:
        return False
    
    # Global admins can access everything
    if user.has_role(Role.ADMIN):
        return True
    
    # Get user's campus scope
    user_campus = get_user_campus_scope(user)
    
    # If user has no campus restriction, allow access
    if user_campus is None:
        return True
    
    # If checking for None/All campuses, campus admins cannot access
    if campus is None:
        return False
    
    # Campus admin can only access their campus
    return user_campus.id == campus.id


def campus_admin_required(view_func):
    """
    Decorator to require campus admin or global admin role.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentication required")
        
        if not (request.user.has_role(Role.ADMIN) or request.user.has_role(Role.CAMPUS_ADMIN)):
            return HttpResponseForbidden("Admin or Campus Admin role required")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def enforce_campus_scope(queryset, user, campus_field='campus'):
    """
    Filter queryset based on user's campus scope.
    
    Args:
        queryset: Django queryset to filter
        user: User object
        campus_field: Name of the campus foreign key field (default: 'campus')
    
    Returns:
        Filtered queryset
    """
    user_campus = get_user_campus_scope(user)
    
    # Global admins see everything
    if user_campus is None:
        return queryset
    
    # Campus admins only see their campus
    filter_kwargs = {f'{campus_field}': user_campus}
    return queryset.filter(**filter_kwargs)


def get_accessible_campuses(user):
    """
    Get list of campuses the user can access.
    
    Returns:
        QuerySet of Campus objects the user can access
    """
    from apps.tenant.orgsettings.services import get_or_create_organization
    
    # Global admins can access all campuses
    if user.has_role(Role.ADMIN):
        org = get_or_create_organization()
        return Campus.objects.filter(organization=org, is_active=True)
    
    # Campus admins can only access their campus
    user_campus = get_user_campus_scope(user)
    if user_campus:
        return Campus.objects.filter(id=user_campus.id)
    
    # Other users have no campus access restrictions at this level
    from apps.tenant.orgsettings.services import get_or_create_organization
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org, is_active=True)


def validate_campus_access(user, campus_id: Optional[int]) -> bool:
    """
    Validate if user can access the specified campus.
    
    Args:
        user: User object
        campus_id: Campus ID to check (None means "All campuses")
    
    Returns:
        True if access is allowed, False otherwise
    """
    if campus_id is None:
        # Only global admins can view "All campuses"
        return user.has_role(Role.ADMIN)
    
    try:
        campus = Campus.objects.get(id=campus_id)
        return user_can_access_campus(user, campus)
    except Campus.DoesNotExist:
        return False
