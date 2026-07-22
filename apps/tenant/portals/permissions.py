from __future__ import annotations

from collections.abc import Iterable
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .role_navigation import ADMIN_PORTAL_ROLE_CODES


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _normalise_role_codes(role_codes) -> tuple[str, ...]:
    """Accept one role code or an iterable without silently denying everyone."""

    if isinstance(role_codes, str):
        return (role_codes,)
    if isinstance(role_codes, Iterable):
        values = tuple(code for code in role_codes if isinstance(code, str) and code)
        if values:
            return values
    raise TypeError("A role code or a non-empty iterable of role codes is required.")


def roles_required(*role_codes: str):
    """Allow the view if the user has any supplied role or is a superuser."""

    allowed_codes = _normalise_role_codes(role_codes)

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if _is_superuser(user):
                return view_func(request, *args, **kwargs)
            if hasattr(user, "has_role") and any(user.has_role(code) for code in allowed_codes):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Forbidden")

        return _wrapped

    return decorator


def role_required(role_code):
    """Require one role; iterable input is supported defensively for legacy code."""

    return roles_required(*_normalise_role_codes(role_code))


# Every role intentionally rendered in the administrator shell must pass the
# corresponding portal guard. Principals are tenant-wide school leaders.
admin_portal_required = roles_required(*ADMIN_PORTAL_ROLE_CODES)
