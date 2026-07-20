from __future__ import annotations

from apps.tenant.orgsettings.services import get_current_campus, get_organization

from .configuration import resolve_effective_terminology
from .models import CampusEducationStage, InstitutionEducationProfile
from .services import NEUTRAL_TERMINOLOGY


def get_institution_education_profile() -> InstitutionEducationProfile | None:
    """Return the configured profile without creating or changing tenant data."""

    organization = get_organization()
    if organization is None:
        return None
    return InstitutionEducationProfile.objects.select_related(
        "organization",
        "primary_framework",
    ).filter(
        organization=organization,
        is_active=True,
    ).first()


def get_request_campus_stage(
    request,
    *,
    stage_code: str | None = None,
) -> CampusEducationStage | None:
    profile = get_institution_education_profile()
    if profile is None:
        return None
    campus = get_current_campus(request) if request is not None else None
    queryset = profile.campus_stages.select_related(
        "stage",
        "framework_stage",
        "campus",
    ).filter(is_active=True)
    if campus is not None:
        queryset = queryset.filter(campus=campus)
    if stage_code:
        queryset = queryset.filter(stage__code=stage_code)
    return queryset.order_by("stage__order", "id").first()


def terminology_for_request(
    request=None,
    *,
    stage_code: str | None = None,
) -> dict[str, str]:
    """Return effective labels for gradual adoption by existing views and templates."""

    profile = get_institution_education_profile()
    if profile is None:
        return dict(NEUTRAL_TERMINOLOGY)
    campus_stage = (
        get_request_campus_stage(request, stage_code=stage_code)
        if request is not None
        else None
    )
    return resolve_effective_terminology(
        profile=profile,
        campus_stage=campus_stage,
    )


def assessment_aliases_for_request(request=None) -> dict[str, str]:
    """Return local assessment aliases such as BOT, MOT, EOT and AOI."""

    profile = get_institution_education_profile()
    if (
        profile is None
        or not profile.use_local_terminology
        or not profile.primary_framework_id
    ):
        return {}
    settings = dict(profile.primary_framework.default_settings or {})
    aliases = dict(settings.get("assessment_aliases") or {})
    aliases.update(
        dict((profile.settings or {}).get("assessment_aliases") or {})
    )
    return {
        str(key): str(value)
        for key, value in aliases.items()
        if str(key).strip() and str(value).strip()
    }


def framework_aliases_for_request(request=None) -> dict[str, str]:
    """Return all local aliases exposed to templates, including MDD."""

    aliases = assessment_aliases_for_request(request)
    profile = get_institution_education_profile()
    if (
        profile is None
        or not profile.use_local_terminology
        or not profile.primary_framework_id
    ):
        return aliases

    framework_settings = dict(
        profile.primary_framework.default_settings or {}
    )
    profile_settings = dict(profile.settings or {})
    performing_arts_alias = str(
        profile_settings.get(
            "performing_arts_alias",
            framework_settings.get("performing_arts_alias", ""),
        )
        or ""
    ).strip()
    performing_arts_label = str(
        profile_settings.get(
            "performing_arts_label",
            "Music, Dance and Drama",
        )
        or ""
    ).strip()
    if performing_arts_alias and performing_arts_label:
        aliases[performing_arts_alias] = performing_arts_label

    aliases.update(
        {
            str(key): str(value)
            for key, value in dict(
                framework_settings.get("terminology_aliases") or {}
            ).items()
            if str(key).strip() and str(value).strip()
        }
    )
    aliases.update(
        {
            str(key): str(value)
            for key, value in dict(
                profile_settings.get("terminology_aliases") or {}
            ).items()
            if str(key).strip() and str(value).strip()
        }
    )
    return aliases


def external_exam_aliases_for_request(request=None) -> list[str]:
    profile = get_institution_education_profile()
    if (
        profile is None
        or not profile.use_local_terminology
        or not profile.primary_framework_id
    ):
        return []
    settings = dict(profile.primary_framework.default_settings or {})
    values = list(settings.get("external_exam_aliases") or [])
    custom_values = list(
        (profile.settings or {}).get("external_exam_aliases") or []
    )
    result: list[str] = []
    seen: set[str] = set()
    for value in [*values, *custom_values]:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
