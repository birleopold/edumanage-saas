from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from apps.tenant.users.models import Role


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def role_required(role_code: str):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if _is_superuser(user):
                return view_func(request, *args, **kwargs)
            if hasattr(user, "has_role") and user.has_role(role_code):
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
                return view_func(request, *args, **kwargs)
            if hasattr(user, "has_role") and any(user.has_role(r) for r in role_codes):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Forbidden")

        return _wrapped

    return decorator


# Global tenant admin UI: full admins, campus-scoped admins, and Django superusers.
admin_portal_required = roles_required(Role.ADMIN, Role.CAMPUS_ADMIN)
