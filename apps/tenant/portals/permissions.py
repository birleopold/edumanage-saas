from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from apps.tenant.users.models import Role
from .campus_permissions import get_user_campus_scope


def role_required(role_code: str):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if hasattr(user, "has_role") and user.has_role(role_code):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Forbidden")

        return _wrapped

    return decorator
