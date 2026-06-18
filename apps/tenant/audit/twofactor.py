import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenant.users.models import Role

from .models import UserTwoFactorSetting


def user_needs_2fa(user):
    if not getattr(settings, "ADMIN_2FA_REQUIRED", False):
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    return hasattr(user, "has_role") and (user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN))


def generate_code(request):
    code = f"{random.randint(100000, 999999)}"
    request.session["two_factor_code"] = code
    request.session["two_factor_code_at"] = timezone.now().isoformat()
    if request.user.email:
        send_mail("EduManage verification code", f"Your verification code is {code}.", getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@edumanage.local"), [request.user.email], fail_silently=True)
    return code


@login_required
def verify_2fa(request):
    setting, _ = UserTwoFactorSetting.objects.get_or_create(user=request.user)
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()
        if code and code == request.session.get("two_factor_code"):
            request.session["admin_2fa_verified"] = True
            setting.last_verified_at = timezone.now()
            setting.is_enabled = True
            setting.save(update_fields=["last_verified_at", "is_enabled"])
            messages.success(request, "Verification complete.")
            return redirect("admin_home")
        messages.error(request, "Invalid verification code.")
    generate_code(request)
    return render(request, "portals/audit/verify_2fa.html", {"setting": setting})
