"""Professional, traceable error handlers for production pages."""

from django.conf import settings
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from apps.tenant.audit.request_ids import apply_request_id, ensure_request_id
from apps.tenant.users.models import Role


def _safe_reverse(name, fallback):
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


def _dashboard_action(request):
    """Return the safest useful destination for the signed-in account."""

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return "Sign in", _safe_reverse("login", "/login/")

    has_role = getattr(user, "has_role", None)
    if callable(has_role):
        if has_role(Role.ADMIN) or has_role(Role.CAMPUS_ADMIN):
            return "Back to dashboard", _safe_reverse("admin_home", "/admin/")
        if has_role(Role.TEACHER):
            return "Back to dashboard", _safe_reverse("teacher_home", "/teacher/")
        if has_role(Role.STUDENT):
            return "Back to dashboard", _safe_reverse("student_home", "/student/")
        if has_role(Role.PARENT):
            return "Back to dashboard", _safe_reverse("parent_home", "/parent/")

    return "Open my profile", _safe_reverse("user_profile", "/profile/")


def _error_context(
    request,
    code,
    title,
    message,
    *,
    icon="ph-warning",
    action_label=None,
    action_url=None,
    support_hint=None,
    secondary_action_label=None,
    secondary_action_url=None,
):
    default_label, default_url = _dashboard_action(request)
    return {
        "error_code": code,
        "error_title": title,
        "error_message": message,
        "error_icon": icon,
        "action_label": action_label or default_label,
        "action_url": action_url or default_url,
        "secondary_action_label": secondary_action_label,
        "secondary_action_url": secondary_action_url,
        "support_hint": support_hint,
        "support_contact_email": getattr(settings, "SUPPORT_CONTACT_EMAIL", ""),
        "request_reference": ensure_request_id(request),
    }


def render_error_page(request, template_name, status, context):
    response = render(request, template_name, context=context, status=status)
    return apply_request_id(response, request)


def handler400(request, exception=None):
    """Friendly bad request / invalid-domain style page."""

    return render_error_page(
        request,
        "errors/invalid_domain.html",
        400,
        _error_context(
            request,
            "400",
            "Invalid request",
            "This request could not be accepted safely. Check the address and try again, or contact support if the problem continues.",
            icon="ph-globe-x",
            action_label="Open platform home",
            action_url="/",
            support_hint="If this is a newly added custom domain, its DNS records may still be updating.",
        ),
    )


def handler404(request, exception=None):
    """Custom 404 error handler."""

    return render_error_page(
        request,
        "errors/404.html",
        404,
        _error_context(
            request,
            "404",
            "Page not found",
            "The page may have moved, been renamed, or no longer be available to your account.",
            icon="ph-map-trifold",
        ),
    )


def handler403(request, exception=None):
    """Custom 403 error handler."""

    return render_error_page(
        request,
        "errors/403.html",
        403,
        _error_context(
            request,
            "403",
            "Access denied",
            "Your account does not have permission to open this area. Contact your school administrator if you believe your access should be updated.",
            icon="ph-lock-key",
        ),
    )


def csrf_failure(request, reason=""):
    """Explain an expired or rejected form safely without exposing internals."""

    dashboard_label, dashboard_url = _dashboard_action(request)
    return render_error_page(
        request,
        "errors/403.html",
        403,
        _error_context(
            request,
            "403",
            "Your form session expired",
            "For your protection, the security check for this form could not be completed. No changes were saved. Open the form again and resubmit it.",
            icon="ph-shield-warning",
            action_label="Open the form again",
            action_url=getattr(request, "path", "") or "/",
            secondary_action_label=dashboard_label,
            secondary_action_url=dashboard_url,
            support_hint="This can happen after a long period of inactivity, signing in on another tab, or using an old form page.",
        ),
    )


def handler500(request):
    """Custom 500 error handler."""

    dashboard_label, dashboard_url = _dashboard_action(request)
    return render_error_page(
        request,
        "errors/500.html",
        500,
        _error_context(
            request,
            "500",
            "System temporarily unavailable",
            "Something went wrong while loading this page. The technical details have been kept private and the request reference can be used for support follow-up.",
            icon="ph-cloud-warning",
            action_label="Try this page again",
            action_url=getattr(request, "path", "") or "/",
            secondary_action_label=dashboard_label,
            secondary_action_url=dashboard_url,
            support_hint="If the problem continues, contact support and quote the request reference shown below.",
        ),
    )


def system_unavailable(request):
    dashboard_label, dashboard_url = _dashboard_action(request)
    return render_error_page(
        request,
        "errors/503.html",
        503,
        _error_context(
            request,
            "503",
            "System temporarily unavailable",
            "EduManage cannot complete this request at the moment. Please try again shortly.",
            icon="ph-cloud-warning",
            action_label="Try this page again",
            action_url=getattr(request, "path", "") or "/",
            secondary_action_label=dashboard_label,
            secondary_action_url=dashboard_url,
        ),
    )


def tenant_suspended(request):
    tenant = getattr(request, "tenant", None)
    school_name = getattr(tenant, "name", "This school")
    return render_error_page(
        request,
        "errors/tenant_suspended.html",
        403,
        _error_context(
            request,
            "403",
            "School portal unavailable",
            f"{school_name} is temporarily suspended. Access is paused until the account is reactivated by the platform owner.",
            icon="ph-pause-circle",
            action_label="Open platform home",
            action_url="/",
            support_hint="School data remains protected while the account is suspended.",
        ),
    )


def invalid_domain(request):
    return render_error_page(
        request,
        "errors/invalid_domain.html",
        400,
        _error_context(
            request,
            "400",
            "Invalid school address",
            "This web address is not connected to an active EduManage school. Check the domain name or contact support.",
            icon="ph-globe-x",
            action_label="Open platform home",
            action_url="/",
            support_hint="If this is a newly added custom domain, its DNS records may still be updating.",
        ),
    )
