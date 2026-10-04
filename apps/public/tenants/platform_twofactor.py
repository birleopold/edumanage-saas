import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import PlatformTwoFactorSetting


def platform_2fa_required(user):
    return bool(getattr(user, "is_authenticated", False) and user.is_superuser and getattr(settings, "PLATFORM_2FA_REQUIRED", True))


def _digest(code):
    return salted_hmac("edumanage.platform-2fa", code).hexdigest()


def _clear(request):
    for key in ("platform_2fa_digest", "platform_2fa_at", "platform_2fa_attempts"):
        request.session.pop(key, None)


def _send(request):
    if not request.user.email:
        raise ValueError("Platform superuser requires an email address.")
    code = f"{secrets.randbelow(900000) + 100000:06d}"
    request.session["platform_2fa_digest"] = _digest(code)
    request.session["platform_2fa_at"] = timezone.now().isoformat()
    request.session["platform_2fa_attempts"] = 0
    send_mail(
        "EduManage Platform verification code",
        f"Your EduManage Platform Console verification code is {code}.",
        settings.DEFAULT_FROM_EMAIL,
        [request.user.email],
        fail_silently=False,
    )


def _valid(request, code):
    digest = request.session.get("platform_2fa_digest") or ""
    created = request.session.get("platform_2fa_at")
    if not digest or not created:
        return False
    try:
        created_at = timezone.datetime.fromisoformat(created)
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at)
    except (TypeError, ValueError):
        return False
    if timezone.now() - created_at > timedelta(seconds=getattr(settings, "PLATFORM_2FA_CODE_TTL_SECONDS", 600)):
        return False
    return constant_time_compare(digest, _digest(code))


@login_required
def platform_verify_2fa(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Platform verification is restricted to superusers.")
    setting, _ = PlatformTwoFactorSetting.objects.get_or_create(user=request.user)
    if request.method == "POST":
        attempts = int(request.session.get("platform_2fa_attempts", 0)) + 1
        request.session["platform_2fa_attempts"] = attempts
        code = (request.POST.get("code") or "").strip()
        if attempts <= getattr(settings, "PLATFORM_2FA_MAX_ATTEMPTS", 5) and code and _valid(request, code):
            request.session["platform_2fa_verified"] = True
            _clear(request)
            setting.is_enabled = True
            setting.last_verified_at = timezone.now()
            setting.save(update_fields=["is_enabled", "last_verified_at", "updated_at"])
            messages.success(request, "Platform verification complete.")
            return redirect("platform_dashboard")
        if attempts >= getattr(settings, "PLATFORM_2FA_MAX_ATTEMPTS", 5):
            _clear(request)
            messages.error(request, "Too many attempts. Request a new verification code.")
        else:
            messages.error(request, "Invalid or expired verification code.")
    if not request.session.get("platform_2fa_digest"):
        try:
            _send(request)
        except Exception:
            messages.error(request, "We could not send the Platform verification code. Contact support.")
    return render(request, "platform/verify_2fa.html", {"setting": setting})
