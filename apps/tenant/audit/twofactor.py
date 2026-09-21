import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils.crypto import constant_time_compare, salted_hmac
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenant.portals.role_navigation import portal_home_url_for
from apps.tenant.users.models import Role

from .models import UserTwoFactorSetting


def _eligible_for_admin_2fa(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return hasattr(user, "has_role") and (
        user.has_role(Role.ADMIN)
        or user.has_role(Role.CAMPUS_ADMIN)
        or user.has_role(Role.PRINCIPAL)
    )


def user_needs_2fa(user):
    """Require OTP only when globally enforced or enabled for this account.

    Email OTP is deliberately opt-in for school administrators. The production
    setting remains available as an emergency global enforcement switch, but it
    is disabled by default.
    """
    if not _eligible_for_admin_2fa(user):
        return False
    if getattr(settings, "ADMIN_2FA_REQUIRED", False):
        return True
    try:
        return UserTwoFactorSetting.objects.filter(user=user, is_enabled=True).exists()
    except Exception:
        if getattr(settings, "ADMIN_2FA_REQUIRED", False):
            raise
        return False


def _code_digest(code):
    return salted_hmac("edumanage.admin-2fa", code).hexdigest()


def _clear_code(request):
    for key in ("two_factor_code_digest", "two_factor_code_at", "two_factor_attempts"):
        request.session.pop(key, None)


def _code_is_current(request, code):
    created_raw = request.session.get("two_factor_code_at")
    digest = request.session.get("two_factor_code_digest") or ""
    if not created_raw or not digest:
        return False
    try:
        created = timezone.datetime.fromisoformat(created_raw)
        if timezone.is_naive(created):
            created = timezone.make_aware(created)
    except (TypeError, ValueError):
        return False
    ttl_seconds = getattr(settings, "ADMIN_2FA_CODE_TTL_SECONDS", 600)
    if timezone.now() - created > timedelta(seconds=ttl_seconds):
        return False
    return constant_time_compare(digest, _code_digest(code))


def generate_code(request):
    code = f"{secrets.randbelow(900000) + 100000:06d}"
    request.session["two_factor_code_digest"] = _code_digest(code)
    request.session["two_factor_code_at"] = timezone.now().isoformat()
    request.session["two_factor_attempts"] = 0
    if not request.user.email:
        raise ValueError("An email address is required for two-step verification.")
    send_mail(
        "EduManage verification code",
        f"Your verification code is {code}.",
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@edumanage.local"),
        [request.user.email],
        fail_silently=False,
    )
    return code


@login_required
def two_factor_settings(request):
    if not _eligible_for_admin_2fa(request.user):
        return HttpResponseForbidden("Two-step verification is available to school administrators only.")

    setting, _ = UserTwoFactorSetting.objects.get_or_create(user=request.user)
    globally_required = bool(getattr(settings, "ADMIN_2FA_REQUIRED", False))

    if request.method == "POST":
        enabled = request.POST.get("enabled") == "1"
        if globally_required and not enabled:
            messages.error(request, "Verification codes are currently required by the platform administrator.")
            return redirect("audit_two_factor_settings")

        setting.is_enabled = enabled
        setting.save()
        request.session.pop("admin_2fa_verified", None)
        _clear_code(request)

        if enabled:
            messages.success(request, "Verification codes are enabled. Complete one verification to finish setup.")
            return redirect("audit_verify_2fa")

        messages.success(request, "Verification codes have been disabled for your account.")
        return redirect("audit_two_factor_settings")

    return render(
        request,
        "portals/audit/two_factor_settings.html",
        {"setting": setting, "globally_required": globally_required},
    )


@login_required
def verify_2fa(request):
    if not _eligible_for_admin_2fa(request.user):
        return HttpResponseForbidden("Verification codes are available to administrator accounts only.")

    setting, _ = UserTwoFactorSetting.objects.get_or_create(user=request.user)
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()
        attempts = int(request.session.get("two_factor_attempts", 0)) + 1
        request.session["two_factor_attempts"] = attempts
        max_attempts = getattr(settings, "ADMIN_2FA_MAX_ATTEMPTS", 5)
        if attempts <= max_attempts and code and _code_is_current(request, code):
            request.session["admin_2fa_verified"] = True
            _clear_code(request)
            setting.last_verified_at = timezone.now()
            setting.is_enabled = True
            setting.save(update_fields=["last_verified_at", "is_enabled"])
            messages.success(request, "Verification complete.")
            return redirect(portal_home_url_for(request.user))
        if attempts >= max_attempts:
            _clear_code(request)
            messages.error(request, "Too many attempts. A new code has been sent.")
        else:
            messages.error(request, "Invalid or expired verification code.")
    if not request.session.get("two_factor_code_digest"):
        try:
            generate_code(request)
        except Exception:
            messages.error(request, "We could not send a verification code. Please contact support.")
    return render(request, "portals/audit/verify_2fa.html", {"setting": setting})
