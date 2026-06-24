from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect

from .services import get_current_campus, get_feature_flags, get_organization, normalize_feature_code


FEATURE_ROUTE_PREFIXES = {
    "ACADEMICS": ("/admin/academics/",),
    "ADMISSIONS": ("/admin/admissions/",),
    "ATTENDANCE": ("/admin/attendance/",),
    "ASSESSMENTS": ("/admin/assessments/",),
    "ANNOUNCEMENTS": ("/admin/announcements/",),
    "COURSEWORK": ("/admin/coursework/", "/teacher/coursework/", "/student/coursework/"),
    "FINANCE": ("/admin/finance/", "/parent/finance/", "/student/finance/"),
    "EXAMS": ("/admin/exams/",),
    "REPORTS": ("/admin/reports/",),
    "DOCUMENTS": ("/admin/documents/",),
    "TIMETABLE": ("/admin/timetable/",),
    "TRANSPORT": ("/admin/transport/",),
    "LIBRARY": ("/admin/library/",),
    "HOSTELS": ("/admin/hostels/",),
    "INVENTORY": ("/admin/inventory/",),
    "HR": ("/admin/hr/",),
    "DISCIPLINE": ("/admin/discipline/",),
    "MESSAGING": ("/messages/", "/message-ops/"),
    "ANALYTICS": ("/admin/analytics/",),
    "AUDIT": ("/admin/audit/",),
    "INTEGRATIONS": ("/admin/integrations/",),
    "MOBILE_API": ("/api/v1/mobile/",),
}

ALWAYS_ALLOWED_PREFIXES = (
    "/admin/",
    "/admin/settings/",
    "/admin/school-setup/",
    "/admin/system-status/",
    "/notifications/",
    "/health/",
    "/static/",
    "/media/",
)


class FeatureGateMiddleware:
    """Hide/deny tenant modules that the school owner has disabled.

    The feature flags only remove access to selected modules. They do not change
    tenant data, migrations, or the rest of the system, so enabled modules keep
    working normally.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        blocked_feature = self._blocked_feature(request)
        if blocked_feature:
            messages.warning(request, f"{blocked_feature.replace('_', ' ').title()} is turned off for this school.")
            return redirect("admin_home")
        return self.get_response(request)

    def _blocked_feature(self, request):
        schema_name = getattr(connection, "schema_name", "public") or "public"
        if schema_name == "public":
            return None

        path = request.path or ""
        if path in {"/admin/", "/teacher/", "/student/", "/parent/"}:
            return None
        if path.startswith("/admin/settings/feature-flags/"):
            return None
        if path.startswith("/admin/settings/") or path.startswith("/admin/school-setup/") or path.startswith("/admin/system-status/"):
            return None
        if path.startswith("/static/") or path.startswith("/media/") or path.startswith("/health/"):
            return None

        org = get_organization()
        campus = get_current_campus(request)
        flags = get_feature_flags(org, campus)
        for feature, prefixes in FEATURE_ROUTE_PREFIXES.items():
            if flags.get(normalize_feature_code(feature), True):
                continue
            if any(path.startswith(prefix) for prefix in prefixes):
                return feature
        return None
