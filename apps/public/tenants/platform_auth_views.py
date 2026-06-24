from django.contrib import messages
from django.contrib.auth import login
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


def platform_login(request):
    """Public platform login view.

    This view must not use platform_admin_required; otherwise anonymous users are
    redirected back to the login page repeatedly with nested next parameters.
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect(_safe_platform_next_url(request))
        messages.error(request, "This account is not allowed to access the Platform Console.")
        return redirect("landing_page")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not user.is_superuser:
            messages.error(request, "This account is not allowed to access the Platform Console.")
        else:
            login(request, user)
            messages.success(request, "Welcome to the Platform Console.")
            return redirect(_safe_platform_next_url(request))

    next_url = request.GET.get("next", "")
    if next_url.startswith(reverse("platform_admin_login")):
        next_url = ""
    return render(request, "platform/login.html", {"form": form, "next": next_url})
