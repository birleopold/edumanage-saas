from typing import Dict, Optional

from django.db import connection

from .models import Campus, FeatureFlag, OrganizationProfile


SESSION_CURRENT_CAMPUS_ID = "orgsettings_current_campus_id"

DEFAULT_FLAG_CODES = [
    "ATTENDANCE",
    "ASSESSMENTS",
    "FINANCE",
    "EXAMS",
    "REPORTS",
    "DOCUMENTS",
    "ANNOUNCEMENTS",
    "DISCIPLINE",
    "TIMETABLE",
    "TRANSPORT",
    "LIBRARY",
    "HOSTELS",
    "INVENTORY",
    "ADMISSIONS",
    "HR",
]


def get_organization() -> Optional[OrganizationProfile]:
    if getattr(connection, "schema_name", None) == "public":
        return None
    # Use select_related to avoid N+1 queries and ensure fresh data
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


def get_feature_flags(org: Optional[OrganizationProfile], campus: Optional[Campus]) -> Dict[str, bool]:
    if getattr(connection, "schema_name", None) == "public":
        return {}

    flags: Dict[str, bool] = {code: True for code in DEFAULT_FLAG_CODES}

    if org is None:
        return flags

    for ff in FeatureFlag.objects.filter(campus__isnull=True):
        flags[ff.code] = bool(ff.is_enabled)

    if campus is not None:
        for ff in FeatureFlag.objects.filter(campus=campus):
            flags[ff.code] = bool(ff.is_enabled)

    return flags
