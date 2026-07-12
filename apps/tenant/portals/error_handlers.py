"""
Professional error handlers for friendly production pages.
"""

from django.http import HttpResponse
from django.template.loader import render_to_string


def _error_context(code, title, message, *, icon="ph-warning", action_label="Go to home", action_url="/", support_hint=None):
    return {
        "error_code": code,
        "error_title": title,
        "error_message": message,
        "error_icon": icon,
        "action_label": action_label,
        "action_url": action_url,
        "support_hint": support_hint,
    }


def render_error_page(request, template_name, status, context):
    content = render_to_string(template_name, context)
    return HttpResponse(content, status=status)


def handler400(request, exception=None):
    """Friendly bad request / invalid-domain style page."""
    return render_error_page(
        request,
        "errors/invalid_domain.html",
        400,
        _error_context(
            "400",
            "Invalid domain",
            "This web address is not connected to an active EduManage school. Please check the domain name or contact support.",
            icon="ph-globe-x",
            action_label="Open platform home",
            action_url="/",
            support_hint="If this is a newly added custom domain, DNS may still be propagating.",
        ),
    )


def handler404(request, exception=None):
    """Custom 404 error handler."""
    return render_error_page(
        request,
        "errors/404.html",
        404,
        _error_context(
            "404",
            "Page not found",
            "The page you are looking for may have moved, been renamed, or is no longer available.",
            icon="ph-map-trifold",
            action_label="Back to dashboard",
            action_url="/",
        ),
    )


def handler403(request, exception=None):
    """Custom 403 error handler."""
    return render_error_page(
        request,
        "errors/403.html",
        403,
        _error_context(
            "403",
            "Access denied",
            "Your account does not have permission to open this area. Please contact your school administrator if you believe this is a mistake.",
            icon="ph-lock-key",
            action_label="Back to dashboard",
            action_url="/",
        ),
    )


def handler500(request):
    """Custom 500 error handler."""
    return render_error_page(
        request,
        "errors/500.html",
        500,
        _error_context(
            "500",
            "System temporarily unavailable",
            "Something went wrong while loading this page. The EduManage team can review the error without exposing technical details to users.",
            icon="ph-cloud-warning",
            action_label="Try again",
            action_url=getattr(request, "path", "/") or "/",
            support_hint="If the problem continues, contact support with the time and page you were trying to open.",
        ),
    )


def system_unavailable(request):
    return render_error_page(
        request,
        "errors/503.html",
        503,
        _error_context(
            "503",
            "System temporarily unavailable",
            "EduManage is currently unable to complete this request. Please try again shortly.",
            icon="ph-cloud-warning",
            action_label="Try again",
            action_url=getattr(request, "path", "/") or "/",
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
            "403",
            "School Portal Unavailable",
            f"{school_name} is temporarily suspended. Access to this school system is paused until the account is reactivated by the platform owner.",
            icon="ph-pause-circle",
            action_label="Contact school administration",
            action_url="/",
            support_hint="School data remains protected while the account is suspended.",
        ),
    )


def invalid_domain(request):
    return handler400(request)
