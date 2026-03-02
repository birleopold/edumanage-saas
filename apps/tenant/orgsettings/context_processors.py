from django.db import connection
from django.utils import timezone

from .services import get_current_campus, get_feature_flags, get_or_create_organization


def orgsettings(request):
    if getattr(connection, "schema_name", None) == "public":
        return {}

    org = get_or_create_organization()
    campus = get_current_campus(request)

    campuses = []
    if org:
        campuses = list(org.campuses.filter(is_active=True).order_by("name"))

    # Add cache-busting timestamp for static assets
    cache_buster = int(timezone.now().timestamp())

    return {
        "org_profile": org,
        "current_campus": campus,
        "campuses": campuses,
        "feature_flags": get_feature_flags(org, campus),
        "cache_buster": cache_buster,
    }
