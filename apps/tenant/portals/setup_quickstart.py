"""Safe, explicit quick-start actions for the School Setup Center.

These helpers deliberately operate on the existing authoritative academic and
education-framework models. They never delete, rename, or silently reactivate
administrator-managed records.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.tenant.academics.models import Level
from apps.tenant.education_frameworks.configuration import sync_framework_stage_links
from apps.tenant.education_frameworks.models import InstitutionEducationProfile
from apps.tenant.education_frameworks.services import (
    enable_mapped_stages,
    map_existing_levels,
)

from .setup_center import _uganda_reference_for_type


UGANDA_STANDARD_LEVEL_ORDER = {
    "P1": 10,
    "P2": 20,
    "P3": 30,
    "P4": 40,
    "P5": 50,
    "P6": 60,
    "P7": 70,
    "S1": 110,
    "S2": 120,
    "S3": 130,
    "S4": 140,
    "S5": 150,
    "S6": 160,
}


def is_uganda_standard_level_quickstart_available(
    profile: InstitutionEducationProfile,
) -> bool:
    framework = getattr(profile, "primary_framework", None)
    return bool(
        (getattr(profile, "country_code", "") or "").upper() == "UG"
        and framework
        and getattr(framework, "code", "") == "UG-NATIONAL"
        and _uganda_reference_for_type(profile.institution_type)
    )


def uganda_standard_level_plan(
    profile: InstitutionEducationProfile,
) -> list[dict[str, Any]]:
    """Return the non-destructive standard-level plan for an eligible profile."""
    if not is_uganda_standard_level_quickstart_available(profile):
        return []

    plan: list[dict[str, Any]] = []
    for stage in _uganda_reference_for_type(profile.institution_type):
        for name in stage["levels"]:
            plan.append(
                {
                    "name": name,
                    "order": UGANDA_STANDARD_LEVEL_ORDER[name],
                    "stage_code": stage["code"],
                    "exit_exam": stage["exit_exam"],
                }
            )
    return plan


@transaction.atomic
def sync_existing_education_structure(
    profile: InstitutionEducationProfile,
) -> dict[str, Any]:
    """Synchronize mappings and campus-stage links without replacing admin choices."""
    mapping = map_existing_levels(profile)
    campus_stages_created = enable_mapped_stages(profile)
    framework_links = sync_framework_stage_links(profile)
    return {
        "mapping": mapping,
        "campus_stages_created": campus_stages_created,
        "framework_links": framework_links,
    }


@transaction.atomic
def bootstrap_uganda_standard_levels(
    profile: InstitutionEducationProfile,
) -> dict[str, Any]:
    """Create only missing P/S levels for eligible Uganda school profiles.

    Existing records are matched case-insensitively and kept exactly as they
    are. Inactive records remain inactive so this action cannot undo an
    administrator's deliberate deactivation.
    """
    plan = uganda_standard_level_plan(profile)
    if not plan:
        raise ValueError(
            "Uganda standard-level quick start is available only for eligible "
            "Primary, Secondary or Mixed institutions using the Uganda National Curriculum."
        )

    created_levels = 0
    existing_levels = 0
    inactive_preserved = 0
    created_names: list[str] = []

    for row in plan:
        existing = (
            Level.objects.filter(name__iexact=row["name"])
            .order_by("pk")
            .first()
        )
        if existing is not None:
            existing_levels += 1
            if not existing.is_active:
                inactive_preserved += 1
            continue

        Level.objects.create(
            name=row["name"],
            order=row["order"],
            is_active=True,
        )
        created_levels += 1
        created_names.append(row["name"])

    sync_summary = sync_existing_education_structure(profile)
    return {
        "created_levels": created_levels,
        "existing_levels": existing_levels,
        "inactive_preserved": inactive_preserved,
        "created_names": created_names,
        "planned_levels": len(plan),
        "sync": sync_summary,
    }
