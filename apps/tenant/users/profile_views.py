from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.tenant.students.models import StudentProfile
from apps.tenant.students.services import sync_student_user

from .forms import UserProfileForm
from .models import Role


def _has_role(user, role_code: str) -> bool:
    return hasattr(user, "has_role") and user.has_role(role_code)


def portal_presentation(user) -> dict:
    """Return the same portal shell and home used for the user's login role."""

    if (
        getattr(user, "is_superuser", False)
        or _has_role(user, Role.ADMIN)
        or _has_role(user, Role.CAMPUS_ADMIN)
        or _has_role(user, Role.PRINCIPAL)
    ):
        return {
            "base_template": "portals/admin/base.html",
            "home_url": reverse("admin_home"),
            "role_label": "Administrator",
            "can_manage_two_factor": True,
        }
    if _has_role(user, Role.TEACHER):
        return {
            "base_template": "portals/teacher/base.html",
            "home_url": reverse("teacher_home"),
            "role_label": "Teacher",
            "can_manage_two_factor": False,
        }
    if _has_role(user, Role.STUDENT):
        return {
            "base_template": "portals/student/base.html",
            "home_url": reverse("student_home"),
            "role_label": "Student",
            "can_manage_two_factor": False,
        }
    if _has_role(user, Role.PARENT):
        return {
            "base_template": "portals/parent/base.html",
            "home_url": reverse("parent_home"),
            "role_label": "Parent or guardian",
            "can_manage_two_factor": False,
        }
    return {
        "base_template": "base.html",
        "home_url": reverse("landing_page"),
        "role_label": "Account",
        "can_manage_two_factor": False,
    }


@login_required
@require_http_methods(["GET", "POST"])
def user_profile(request):
    """Edit account details without changing the user's active portal shell."""

    presentation = portal_presentation(request.user)
    student = (
        StudentProfile.objects.filter(user=request.user)
        .select_related("campus", "stream", "user")
        .first()
    )
    if student:
        sync_student_user(student)
        request.user.refresh_from_db(fields=["first_name", "last_name", "email"])

    form = UserProfileForm(
        request.POST if request.method == "POST" else None,
        instance=request.user,
    )
    if student:
        for field_name in ("first_name", "last_name"):
            form.fields[field_name].disabled = True
            form.fields[field_name].help_text = (
                "This name comes from the school student record. Contact the school to correct it."
            )

    if request.method == "POST" and form.is_valid():
        user = form.save()
        if student and student.email != user.email:
            student.email = user.email
            student.save(update_fields=["email"])
        messages.success(request, "Your account details have been updated.")
        return redirect("user_profile")

    user_roles = request.user.roles.all() if hasattr(request.user, "roles") else []
    return render(
        request,
        "auth/profile.html",
        {
            "form": form,
            "user_roles": user_roles,
            "portal_base_template": presentation["base_template"],
            "portal_home_url": presentation["home_url"],
            "portal_role_label": presentation["role_label"],
            "can_manage_two_factor": presentation["can_manage_two_factor"],
            "student_profile": student,
            "managed_student_identity": bool(student),
        },
    )
