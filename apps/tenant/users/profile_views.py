from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render

from apps.tenant.portals.permissions import ACTIVE_PORTAL_ROLE_SESSION_KEY

from .forms import UserProfileForm
from .models import Role


_PROFILE_BASE_TEMPLATES = {
    Role.ADMIN: "portals/admin/base.html",
    Role.CAMPUS_ADMIN: "portals/admin/base.html",
    Role.PRINCIPAL: "portals/admin/base.html",
    Role.TEACHER: "portals/teacher/base.html",
    Role.STUDENT: "portals/student/base.html",
    Role.PARENT: "portals/parent/base.html",
}

_PROFILE_ROLE_ORDER = (
    Role.ADMIN,
    Role.CAMPUS_ADMIN,
    Role.PRINCIPAL,
    Role.TEACHER,
    Role.STUDENT,
    Role.PARENT,
)


def _user_can_use_role(user, role_code: str) -> bool:
    if getattr(user, "is_superuser", False):
        return role_code in (Role.ADMIN, Role.CAMPUS_ADMIN, Role.PRINCIPAL)
    return bool(role_code and hasattr(user, "has_role") and user.has_role(role_code))


def _active_profile_role(request) -> str:
    """Resolve a previously authorized portal role without changing privileges."""
    active_role = request.session.get(ACTIVE_PORTAL_ROLE_SESSION_KEY)
    if active_role in _PROFILE_BASE_TEMPLATES and _user_can_use_role(request.user, active_role):
        return active_role

    for role_code in _PROFILE_ROLE_ORDER:
        if _user_can_use_role(request.user, role_code):
            request.session[ACTIVE_PORTAL_ROLE_SESSION_KEY] = role_code
            return role_code

    return Role.ADMIN


@login_required
def user_profile(request):
    """Edit account data while remaining inside the user's authorized portal shell."""
    active_role = _active_profile_role(request)

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("user_profile")
    else:
        form = UserProfileForm(instance=request.user)

    user_roles = request.user.roles.all() if hasattr(request.user, "roles") else []
    student_profile = None
    try:
        student_profile = request.user.student_profile
    except (ObjectDoesNotExist, AttributeError):
        pass

    return render(
        request,
        "auth/profile.html",
        {
            "form": form,
            "user_roles": user_roles,
            "student_profile": student_profile,
            "profile_base_template": _PROFILE_BASE_TEMPLATES[active_role],
            "active_profile_role": active_role,
        },
    )
