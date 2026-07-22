"""
Enhanced authentication views with better UX and login audit tracking.
"""

import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

from apps.tenant.parents.models import ParentProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.students.services import sync_student_user_identity
from apps.tenant.teachers.models import TeacherProfile

from .device_portal import base_template_for
from .forms import (
    CustomLoginForm,
    CustomPasswordChangeForm,
    CustomPasswordResetConfirmForm,
    CustomPasswordResetForm,
    UserProfileForm,
)


logger = logging.getLogger("edumanage.security")

_AUDIT_DISABLED_NOTICE = "Audit is turned off for this school."


def _audit_login(request, username="", user=None, status="SUCCESS", reason=""):
    try:
        from apps.tenant.audit.models import LoginHistory
        from apps.tenant.audit.services import log_audit, log_login

        mapped = (
            LoginHistory.SUCCESS
            if status == "SUCCESS"
            else LoginHistory.FAILED
            if status == "FAILED"
            else LoginHistory.LOGOUT
        )
        log_login(request, username=username, user=user, status=mapped, reason=reason)
        if status in ["SUCCESS", "LOGOUT"]:
            log_audit(
                request,
                action="LOGIN" if status == "SUCCESS" else "LOGOUT",
                metadata={"username": username or getattr(user, "username", "")},
            )
    except Exception:
        # Login and logout must remain available if the audit subsystem is
        # temporarily unavailable, but the failure must not disappear silently.
        logger.warning(
            "Authentication audit recording failed",
            exc_info=True,
            extra={
                "request_context": {
                    "event": status,
                    "path": getattr(request, "path", ""),
                    "user_id": getattr(user, "pk", None),
                }
            },
        )


def _account_page_messages(request):
    """Consume stale session messages and return a safe, deduplicated list."""
    unique_messages = []
    seen = set()

    for message in messages.get_messages(request):
        text = str(message).strip()
        if not text or text == _AUDIT_DISABLED_NOTICE:
            continue
        key = (getattr(message, "level", None), text)
        if key in seen:
            continue
        seen.add(key)
        unique_messages.append(message)

    return unique_messages


def _role_home_url(user) -> str:
    """Return the safest portal landing page for an authenticated tenant user."""
    if hasattr(user, "has_role"):
        from apps.tenant.users.models import Role

        if (
            user.has_role(Role.ADMIN)
            or user.has_role(Role.CAMPUS_ADMIN)
            or user.has_role(Role.PRINCIPAL)
        ):
            return reverse("admin_home")
        if user.has_role(Role.TEACHER):
            return reverse("teacher_home")
        if user.has_role(Role.STUDENT):
            return reverse("student_home")
        if user.has_role(Role.PARENT):
            return reverse("parent_home")
    return reverse("admin_home")


def _role_profile_for(user):
    """Return the authoritative role profile and a human-friendly role label."""
    from apps.tenant.users.models import Role

    if user.has_role(Role.STUDENT):
        return (
            StudentProfile.objects.filter(user=user)
            .select_related("campus", "stream")
            .first(),
            "Student",
        )
    if user.has_role(Role.PARENT):
        return ParentProfile.objects.filter(user=user).first(), "Parent or guardian"
    if user.has_role(Role.TEACHER):
        return (
            TeacherProfile.objects.filter(user=user).select_related("campus").first(),
            "Teacher",
        )
    if user.has_role(Role.CAMPUS_ADMIN):
        return None, "Campus administrator"
    if user.has_role(Role.PRINCIPAL):
        return None, "Principal"
    return None, "Administrator"


def _sync_role_identity(user, profile):
    if profile is None:
        return
    if isinstance(profile, StudentProfile):
        sync_student_user_identity(profile)
        return

    updates = []
    for field_name in ("first_name", "last_name", "email"):
        value = (getattr(profile, field_name, "") or "").strip()
        if getattr(user, field_name) != value:
            setattr(user, field_name, value)
            updates.append(field_name)
    if updates:
        user.save(update_fields=updates)


class CustomLoginView(LoginView):
    """Enhanced login view with remember-me and safe return navigation."""

    form_class = CustomLoginForm
    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        remember_me = form.cleaned_data.get("remember_me")
        if not remember_me:
            self.request.session.set_expiry(0)
        else:
            self.request.session.set_expiry(1209600)
        response = super().form_valid(form)
        _audit_login(
            self.request,
            username=form.cleaned_data.get("username") or "",
            user=self.request.user,
            status="SUCCESS",
        )
        return response

    def form_invalid(self, form):
        username = self.request.POST.get("username") or self.request.POST.get("email") or ""
        _audit_login(
            self.request,
            username=username,
            user=None,
            status="FAILED",
            reason="Invalid credentials",
        )
        return super().form_invalid(form)

    def get_success_url(self):
        user = self.request.user
        if getattr(user, "must_change_password", False):
            return reverse("change_password")

        # LoginView validates this value against the current host and allowed
        # schemes. Honour it so users return to the protected page they chose,
        # while ignoring external or otherwise unsafe redirect targets.
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return _role_home_url(user)


class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.html"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Password reset instructions have been sent to your email address.",
        )
        try:
            from apps.tenant.audit.services import log_audit

            log_audit(
                self.request,
                action="PASSWORD",
                metadata={"event": "password_reset_requested"},
            )
        except Exception:
            logger.warning("Password-reset request audit failed", exc_info=True)
        return super().form_valid(form)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = CustomPasswordResetConfirmForm
    template_name = "auth/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Your password has been reset successfully. You can now log in with your new password.",
        )
        try:
            from apps.tenant.audit.services import log_audit

            log_audit(
                self.request,
                action="PASSWORD",
                metadata={"event": "password_reset_completed"},
            )
        except Exception:
            logger.warning("Password-reset completion audit failed", exc_info=True)
        return super().form_valid(form)


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    password_change_required = bool(getattr(request.user, "must_change_password", False))
    account_messages = _account_page_messages(request)

    if request.method == "POST":
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            if getattr(user, "must_change_password", False):
                user.must_change_password = False
                user.save(update_fields=["must_change_password"])

            try:
                from apps.tenant.audit.services import log_audit

                log_audit(
                    request,
                    action="PASSWORD",
                    metadata={
                        "event": "password_changed",
                        "first_login": password_change_required,
                    },
                )
            except Exception:
                logger.warning(
                    "Password-change audit failed",
                    exc_info=True,
                    extra={"request_context": {"user_id": user.pk}},
                )

            messages.success(request, "Your password has been changed successfully.")
            return redirect(_role_home_url(user))
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(
        request,
        "auth/change_password.html",
        {
            "form": form,
            "password_change_required": password_change_required,
            "account_messages": account_messages,
        },
    )


@login_required
def user_profile(request):
    """Role-locked account page backed by the user's authoritative profile."""
    profile_record, role_label = _role_profile_for(request.user)
    _sync_role_identity(request.user, profile_record)

    is_role_managed = profile_record is not None
    form = None
    if not is_role_managed:
        if request.method == "POST":
            form = UserProfileForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, "Your profile has been updated successfully.")
                return redirect("user_profile")
        else:
            form = UserProfileForm(instance=request.user)
    elif request.method == "POST":
        messages.info(
            request,
            "Your name and contact details are managed from your school record.",
        )
        return redirect("user_profile")

    user_roles = request.user.roles.all() if hasattr(request.user, "roles") else []
    return render(
        request,
        "auth/profile.html",
        {
            "form": form,
            "user_roles": user_roles,
            "profile_record": profile_record,
            "role_label": role_label,
            "profile_base_template": base_template_for(request.user),
            "portal_home_url": _role_home_url(request.user),
            "identity_is_school_managed": is_role_managed,
        },
    )


@require_http_methods(["GET", "POST"])
def logout_view(request):
    user = request.user if request.user.is_authenticated else None
    username = getattr(user, "username", "")
    _audit_login(request, username=username, user=user, status="LOGOUT")
    logout(request)
    return redirect("login")
