"""
Enhanced authentication views with better UX and login audit tracking.
"""
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetConfirmView,
)
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import (
    CustomLoginForm,
    CustomPasswordChangeForm,
    CustomPasswordResetConfirmForm,
    CustomPasswordResetForm,
    UserProfileForm,
)


_AUDIT_DISABLED_NOTICE = "Audit is turned off for this school."


def _audit_login(request, username="", user=None, status="SUCCESS", reason=""):
    try:
        from apps.tenant.audit.models import LoginHistory
        from apps.tenant.audit.services import log_audit, log_login
        mapped = LoginHistory.SUCCESS if status == "SUCCESS" else LoginHistory.FAILED if status == "FAILED" else LoginHistory.LOGOUT
        log_login(request, username=username, user=user, status=mapped, reason=reason)
        if status in ["SUCCESS", "LOGOUT"]:
            log_audit(request, action="LOGIN" if status == "SUCCESS" else "LOGOUT", metadata={"username": username or getattr(user, "username", "")})
    except Exception:
        pass


def _account_page_messages(request):
    """Consume stale session messages and return a safe, deduplicated list.

    A redirect loop can queue the same operational feature notice many times.
    Account-security pages must stay focused on authentication and must not
    expose package-level operational notices to the user.
    """
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

        if user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN) or user.has_role(Role.PRINCIPAL):
            return reverse("admin_home")
        if user.has_role(Role.TEACHER):
            return reverse("teacher_home")
        if user.has_role(Role.STUDENT):
            return reverse("student_home")
        if user.has_role(Role.PARENT):
            return reverse("parent_home")
    return reverse("admin_home")


class CustomLoginView(LoginView):
    """Enhanced login view with remember me functionality."""
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
        _audit_login(self.request, username=form.cleaned_data.get("username") or "", user=self.request.user, status="SUCCESS")
        return response

    def form_invalid(self, form):
        username = self.request.POST.get("username") or self.request.POST.get("email") or ""
        _audit_login(self.request, username=username, user=None, status="FAILED", reason="Invalid credentials")
        return super().form_invalid(form)

    def get_success_url(self):
        """Redirect first-login users to password change, then to their role portal."""
        user = self.request.user
        if getattr(user, "must_change_password", False):
            return reverse("change_password")
        return _role_home_url(user)


class CustomPasswordResetView(PasswordResetView):
    """Enhanced password reset view."""
    form_class = CustomPasswordResetForm
    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.html"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        messages.success(self.request, "Password reset instructions have been sent to your email address.")
        try:
            from apps.tenant.audit.services import log_audit
            log_audit(self.request, action="PASSWORD", metadata={"event": "password_reset_requested"})
        except Exception:
            pass
        return super().form_valid(form)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Enhanced password reset confirmation view."""
    form_class = CustomPasswordResetConfirmForm
    template_name = "auth/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been reset successfully. You can now log in with your new password.")
        try:
            from apps.tenant.audit.services import log_audit
            log_audit(self.request, action="PASSWORD", metadata={"event": "password_reset_completed"})
        except Exception:
            pass
        return super().form_valid(form)


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    """Change a tenant user's password without depending on a portal dashboard shell."""
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
                log_audit(request, action="PASSWORD", metadata={"event": "password_changed", "first_login": password_change_required})
            except Exception:
                pass

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
    """User profile view and edit."""
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("user_profile")
    else:
        form = UserProfileForm(instance=request.user)
    user_roles = []
    if hasattr(request.user, "roles"):
        user_roles = request.user.roles.all()
    return render(request, "auth/profile.html", {"form": form, "user_roles": user_roles})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    user = request.user if request.user.is_authenticated else None
    username = getattr(user, "username", "")
    _audit_login(request, username=username, user=user, status="LOGOUT")
    logout(request)
    return redirect("login")
