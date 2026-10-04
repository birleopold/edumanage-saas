from urllib.parse import urlencode

import hashlib

from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def _safe_platform_next_url(request):
    """Return a safe post-login target without allowing login-to-login loops."""
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    login_url = reverse("platform_admin_login")
    dashboard_url = reverse("platform_dashboard")
    if not next_url:
        return dashboard_url
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return dashboard_url
    if next_url.startswith(login_url):
        return dashboard_url
    return next_url


def _platform_login_redirect():
    query = urlencode({"next": reverse("platform_dashboard")})
    return f"{reverse('platform_admin_login')}?{query}"


def platform_access_denied(request):
    """Safely clear a tenant/wrong-role session on the public platform host."""
    if getattr(request, "user", None) and request.user.is_authenticated:
        logout(request)
    messages.error(request, "Only platform superusers can access the SaaS management console.")
    return redirect(_platform_login_redirect())


def _platform_login_key(request, username):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    remote = (forwarded.split(",", 1)[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")) or "unknown"
    return "platform-login-fail:" + hashlib.sha256(f"{remote}|{(username or '').strip().lower()[:150]}".encode()).hexdigest()


def platform_login(request):
    """Public platform login view.

    This view must not use platform_admin_required; otherwise anonymous users are
    redirected back to the login page repeatedly with nested next parameters.
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect(_safe_platform_next_url(request))
        logout(request)
        messages.error(request, "This account is not allowed to access the Platform Console.")
        return redirect(_platform_login_redirect())

    username = request.POST.get("username", "") if request.method == "POST" else ""
    rate_key = _platform_login_key(request, username)
    if request.method == "POST" and int(cache.get(rate_key, 0) or 0) >= getattr(settings, "LOGIN_FAILURE_LIMIT", 8):
        form = AuthenticationForm(request, data=None)
        form.add_error(None, "Too many failed login attempts. Please try again later.")
        return render(request, "platform/login.html", {"form": form, "next": ""}, status=429)

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not user.is_superuser:
            messages.error(request, "This account is not allowed to access the Platform Console.")
        else:
            cache.delete(rate_key)
            login(request, user)
            request.session.pop("platform_2fa_verified", None)
            request.session["platform_2fa_next"] = _safe_platform_next_url(request)
            messages.info(request, "Complete Platform verification to continue.")
            return redirect("platform_verify_2fa")
    elif request.method == "POST":
        try:
            cache.incr(rate_key)
        except ValueError:
            cache.set(rate_key, 1, timeout=getattr(settings, "LOGIN_FAILURE_WINDOW_SECONDS", 900))
        cache.touch(rate_key, timeout=getattr(settings, "LOGIN_FAILURE_WINDOW_SECONDS", 900))

    next_url = request.GET.get("next", "")
    if next_url.startswith(reverse("platform_admin_login")):
        next_url = ""
    return render(request, "platform/login.html", {"form": form, "next": next_url})
