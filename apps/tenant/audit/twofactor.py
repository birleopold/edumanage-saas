import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
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
        return False


def generate_code(request):
    code = f"{random.randint(100000, 999999)}"
    request.session["two_factor_code"] = code
    request.session["two_factor_code_at"] = timezone.now().isoformat()
    if request.user.email:
        send_mail(
            "EduManage verification code",
            f"Your verification code is {code}.",
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@edumanage.local"),
            [request.user.email],
            fail_silently=True,
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
        request.session.pop("two_factor_code", None)
        request.session.pop("two_factor_code_at", None)

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
        if code and code == request.session.get("two_factor_code"):
            request.session["admin_2fa_verified"] = True
            setting.last_verified_at = timezone.now()
            setting.is_enabled = True
            setting.save(update_fields=["last_verified_at", "is_enabled"])
            messages.success(request, "Verification complete.")
            return redirect(portal_home_url_for(request.user))
        messages.error(request, "Invalid verification code.")
    generate_code(request)
    return render(request, "portals/audit/verify_2fa.html", {"setting": setting})
