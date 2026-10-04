from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import PlatformStaffAccess


ROLE_CAPABILITIES = {
    PlatformStaffAccess.OWNER: {"view", "support", "onboarding", "billing", "lifecycle", "domains"},
    PlatformStaffAccess.SUPPORT: {"view", "support"},
    PlatformStaffAccess.ONBOARDING: {"view", "support", "onboarding", "domains"},
    PlatformStaffAccess.BILLING: {"view", "billing"},
}


def platform_role(user):
    if not getattr(user, "is_authenticated", False):
        return None
    if user.is_superuser:
        return PlatformStaffAccess.OWNER
    access = getattr(user, "platform_staff_access", None)
    if access and access.is_active:
        return access.role
    return None


def platform_can(user, capability):
    role = platform_role(user)
    return bool(role and capability in ROLE_CAPABILITIES.get(role, set()))


def platform_capability_required(capability):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not platform_can(request.user, capability):
                messages.error(request, "Your Platform staff role does not allow that action.")
                return redirect(reverse("platform_access_denied"))
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
