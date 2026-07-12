from typing import Dict, Optional

from django.db import connection

from .models import Campus, FeatureFlag, OrganizationProfile


SESSION_CURRENT_CAMPUS_ID = "orgsettings_current_campus_id"

FEATURE_CATALOG = [
    {"code": "ACADEMICS", "label": "Academics", "description": "Academic years, terms, classes, courses, offerings and enrollments."},
    {"code": "ADMISSIONS", "label": "Admissions", "description": "Leads, applicants, admissions pipeline and application tracking."},
    {"code": "ATTENDANCE", "label": "Attendance", "description": "Student attendance sessions and attendance reports."},
    {"code": "ASSESSMENTS", "label": "Assessments", "description": "Assessments, marks, grading and tabulation."},
    {"code": "ANNOUNCEMENTS", "label": "Announcements", "description": "School announcements and notices."},
    {"code": "COURSEWORK", "label": "Coursework", "description": "Learning materials, assignments and submissions."},
    {"code": "FINANCE", "label": "Finance", "description": "Fees, invoices, payments, receipts and balances."},
    {"code": "EXAMS", "label": "Online Exams", "description": "Exam papers, schedules, attempts and publishing."},
    {"code": "QUIZZES", "label": "Quizzes", "description": "Short quizzes, attempts and quiz-based learner practice."},
    {"code": "REPORTS", "label": "Reports", "description": "Finance, attendance, academic and operational reports."},
    {"code": "DOCUMENTS", "label": "Documents", "description": "School document management and files."},
    {"code": "TIMETABLE", "label": "Timetable", "description": "Class timetable and teaching schedule entries."},
    {"code": "TRANSPORT", "label": "Transport", "description": "Drivers, vehicles, routes, stops, schedules and assignments."},
    {"code": "LIBRARY", "label": "Library", "description": "Books, copies, checkouts, returns, fines and reservations."},
    {"code": "HOSTELS", "label": "Hostels", "description": "Dormitories, rooms, bed allocations and boarding records."},
    {"code": "INVENTORY", "label": "Inventory", "description": "Items, stock, issue logs and school stores."},
    {"code": "HR", "label": "Human Resources", "description": "Staff, departments, payroll, pay grades and allowances."},
    {"code": "DISCIPLINE", "label": "Discipline", "description": "Incidents, consequences and discipline records."},
    {"code": "ACTIVITIES", "label": "Activities", "description": "Co-curricular activities, clubs, events and participation."},
    {"code": "DUTY", "label": "Duty Roster", "description": "Duty schedules and staff responsibilities."},
    {"code": "GRIEVANCES", "label": "Grievances", "description": "Complaints, concerns and grievance tracking."},
    {"code": "MESSAGING", "label": "Messaging", "description": "Inbox, chat, delivery dashboard and parent communication."},
    {"code": "POLLS", "label": "Polls", "description": "Polls, surveys and feedback collection."},
    {"code": "ANALYTICS", "label": "Analytics", "description": "Performance analytics, charts and learner intelligence."},
    {"code": "AUDIT", "label": "Security & Audit", "description": "Activity tracking, exports, backups, permissions and audit logs."},
    {"code": "INTEGRATIONS", "label": "Integrations", "description": "External providers such as SMS, WhatsApp, GPS, payments and APIs."},
    {"code": "MOBILE_API", "label": "PWA & Alerts", "description": "Installable browser portal, PWA push readiness and API access."},
]

DEFAULT_FLAG_CODES = [item["code"] for item in FEATURE_CATALOG]
FEATURE_LABELS = {item["code"]: item["label"] for item in FEATURE_CATALOG}
FEATURE_DESCRIPTIONS = {item["code"]: item["description"] for item in FEATURE_CATALOG}


def normalize_feature_code(code: str) -> str:
    return (code or "").strip().upper()


def get_organization() -> Optional[OrganizationProfile]:
    if getattr(connection, "schema_name", None) == "public":
        return None
    return OrganizationProfile.objects.select_related().order_by("id").first()


def get_or_create_organization() -> OrganizationProfile:
    org = get_organization()
    if org:
        return org
    org = OrganizationProfile.objects.create(name="Organization")
    Campus.objects.create(organization=org, name="Main Campus", is_default=True, is_active=True)
    return org


def get_current_campus(request) -> Optional[Campus]:
    if getattr(connection, "schema_name", None) == "public":
        return None
    org = get_organization()
    if not org:
        return None
    campus_id = request.session.get(SESSION_CURRENT_CAMPUS_ID)
    if campus_id:
        campus = Campus.objects.select_related('organization').filter(organization=org, id=campus_id, is_active=True).first()
        if campus:
            return campus
    campus = Campus.objects.select_related('organization').filter(organization=org, is_default=True, is_active=True).first()
    if campus:
        return campus
    return Campus.objects.select_related('organization').filter(organization=org, is_active=True).order_by("name").first()


def set_current_campus(request, campus: Campus) -> None:
    request.session[SESSION_CURRENT_CAMPUS_ID] = campus.id


def campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def update_current_campus_from_request(request) -> None:
    if "campus" not in request.GET:
        return
    raw = request.GET.get("campus")
    if raw == "":
        request.session.pop(SESSION_CURRENT_CAMPUS_ID, None)
        return
    try:
        campus_id = int(raw)
    except (TypeError, ValueError):
        return
    org = get_or_create_organization()
    campus = Campus.objects.filter(organization=org, id=campus_id, is_active=True).first()
    if campus:
        set_current_campus(request, campus)


def selected_campus_id_from_request(request) -> Optional[int]:
    current = get_current_campus(request)
    if "campus" in request.GET:
        raw = request.GET.get("campus")
        if raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return current.id if current else None


def _apply_flag_rows(flags: Dict[str, bool], queryset) -> Dict[str, bool]:
    for ff in queryset.order_by("updated_at", "id"):
        code = normalize_feature_code(ff.code)
        if code in flags:
            flags[code] = bool(ff.is_enabled)
    return flags


def get_feature_flags(org: Optional[OrganizationProfile], campus: Optional[Campus]) -> Dict[str, bool]:
    if getattr(connection, "schema_name", None) == "public":
        return {}
    flags: Dict[str, bool] = {code: True for code in DEFAULT_FLAG_CODES}
    if org is None:
        return flags
    _apply_flag_rows(flags, FeatureFlag.objects.filter(campus__isnull=True))
    if campus is not None:
        _apply_flag_rows(flags, FeatureFlag.objects.filter(campus=campus))
    return flags


def is_feature_enabled(code: str, campus: Optional[Campus] = None) -> bool:
    org = get_organization()
    return get_feature_flags(org, campus).get(normalize_feature_code(code), True)
