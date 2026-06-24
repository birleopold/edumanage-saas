from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect

from .services import get_current_campus, get_feature_flags, get_organization, normalize_feature_code


FEATURE_ROUTE_PREFIXES = {
    "ACADEMICS": ("/admin/academics/",),
    "ADMISSIONS": ("/admin/admissions/",),
    "ATTENDANCE": ("/admin/attendance/", "/teacher/attendance/", "/student/attendance/", "/parent/attendance/"),
    "ASSESSMENTS": ("/admin/assessments/", "/teacher/assessments/", "/student/results/", "/parent/results/"),
    "ANNOUNCEMENTS": ("/admin/announcements/", "/teacher/announcements/", "/student/announcements/", "/parent/announcements/"),
    "COURSEWORK": ("/admin/coursework/", "/teacher/coursework/", "/student/coursework/", "/parent/coursework/"),
    "FINANCE": ("/admin/finance/", "/parent/finance/", "/student/finance/"),
    "EXAMS": ("/admin/exams/", "/teacher/exams/", "/student/exams/", "/parent/exams/"),
    "QUIZZES": ("/admin/quizzes/", "/teacher/quizzes/", "/student/quizzes/"),
    "REPORTS": ("/admin/reports/",),
    "DOCUMENTS": ("/admin/documents/", "/teacher/documents/", "/student/documents/", "/parent/documents/"),
    "TIMETABLE": ("/admin/timetable/", "/teacher/timetable/", "/student/timetable/"),
    "TRANSPORT": ("/admin/transport/", "/student/transport/", "/parent/transport/"),
    "LIBRARY": ("/admin/library/", "/student/library/", "/parent/library/"),
    "HOSTELS": ("/admin/hostels/", "/student/hostels/", "/parent/hostels/"),
    "INVENTORY": ("/admin/inventory/",),
    "HR": ("/admin/hr/", "/teacher/payroll/"),
    "DISCIPLINE": ("/admin/discipline/", "/teacher/discipline/", "/student/discipline/", "/parent/discipline/"),
    "ACTIVITIES": ("/admin/activities/",),
    "DUTY": ("/admin/duty/",),
    "GRIEVANCES": ("/admin/grievances/", "/teacher/grievances/", "/parent/grievances/"),
    "MESSAGING": ("/messages/", "/message-ops/", "/admin/communication/"),
    "POLLS": ("/admin/polls/",),
    "ANALYTICS": ("/admin/analytics/",),
    "AUDIT": ("/admin/audit/",),
    "INTEGRATIONS": ("/admin/integrations/",),
    "MOBILE_API": ("/api/v1/mobile/",),
}

SAFE_PREFIXES = (
    "/admin/settings/feature-flags/",
    "/admin/settings/",
    "/admin/school-setup/",
    "/admin/system-status/",
    "/notifications/",
    "/health/",
    "/static/",
    "/media/",
    "/manifest.webmanifest",
    "/service-worker.js",
)

PORTAL_HOME_BY_PREFIX = (
    ("/teacher/", "teacher_home"),
    ("/student/", "student_home"),
    ("/parent/", "parent_home"),
    ("/admin/", "admin_home"),
)


class FeatureGateMiddleware:
    """Hide/deny tenant modules that the school owner has disabled.

    Feature flags only remove access to selected modules. They do not delete data,
    change migrations, or affect enabled modules.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        blocked_feature = self._blocked_feature(request)
        if blocked_feature:
            messages.warning(request, f"{blocked_feature.replace('_', ' ').title()} is turned off for this school.")
            return redirect(self._fallback_home_name(request))
        return self.get_response(request)

    def _fallback_home_name(self, request):
        path = request.path or ""
        for prefix, route_name in PORTAL_HOME_BY_PREFIX:
            if path.startswith(prefix):
                return route_name
        return "admin_home"

    def _blocked_feature(self, request):
        schema_name = getattr(connection, "schema_name", "public") or "public"
        if schema_name == "public":
            return None

        path = request.path or ""
        if path in {"/admin/", "/teacher/", "/student/", "/parent/"}:
            return None
        if any(path.startswith(prefix) for prefix in SAFE_PREFIXES):
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
