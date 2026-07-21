from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from apps.tenant.users.models import Role


ACTIVE_PORTAL_ROLE_SESSION_KEY = "active_portal_role"


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _remember_active_portal(request, role_code: str) -> None:
    """Remember only a role the current user has already been authorized to use."""
    if request.session.get(ACTIVE_PORTAL_ROLE_SESSION_KEY) != role_code:
        request.session[ACTIVE_PORTAL_ROLE_SESSION_KEY] = role_code


def role_required(role_code: str):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if _is_superuser(user):
                _remember_active_portal(request, role_code)
                return view_func(request, *args, **kwargs)
            if hasattr(user, "has_role") and user.has_role(role_code):
                _remember_active_portal(request, role_code)
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Forbidden")

        return _wrapped

    return decorator


def roles_required(*role_codes: str):
    """Allow the view if the user has any of the given role codes or is a superuser."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if _is_superuser(user):
                _remember_active_portal(request, role_codes[0] if role_codes else Role.ADMIN)
                return view_func(request, *args, **kwargs)
            if hasattr(user, "has_role"):
                authorized_role = next((role for role in role_codes if user.has_role(role)), None)
                if authorized_role:
                    _remember_active_portal(request, authorized_role)
                    return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Forbidden")

        return _wrapped

    return decorator


# Global tenant admin UI: full admins, campus-scoped admins, and Django superusers.
admin_portal_required = roles_required(Role.ADMIN, Role.CAMPUS_ADMIN)
