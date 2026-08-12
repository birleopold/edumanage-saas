"""Safe, explicit quick-start actions for the School Setup Center.

These helpers deliberately operate on the existing authoritative academic and
education-framework models. They never delete, rename, or silently reactivate
administrator-managed records.
"""

from __future__ import annotations

from typing import Any, Iterable

from django.db import transaction
from django.db.models import Q

from apps.tenant.academics.models import ClassGroup, Level
from apps.tenant.education_frameworks.configuration import sync_framework_stage_links
from apps.tenant.education_frameworks.models import (
    CampusEducationStage,
    EducationStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.education_frameworks.services import (
    enable_mapped_stages,
    map_existing_levels,
)
from apps.tenant.orgsettings.models import Campus

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

SCHOOL_CLASSGROUP_QUICKSTART_TYPES = {
    InstitutionEducationProfile.ECD,
    InstitutionEducationProfile.PRIMARY,
    InstitutionEducationProfile.SECONDARY,
    InstitutionEducationProfile.MIXED,
}


def _uses_uganda_national_framework(profile: InstitutionEducationProfile) -> bool:
    framework = getattr(profile, "primary_framework", None)
    return bool(
        (getattr(profile, "country_code", "") or "").upper() == "UG"
        and framework
        and getattr(framework, "code", "") == "UG-NATIONAL"
    )


def _configured_stage_codes(profile: InstitutionEducationProfile) -> set[str]:
    return set(
        CampusEducationStage.objects.filter(profile=profile, is_active=True)
        .values_list("stage__code", flat=True)
    )


def uganda_standard_level_plan(
    profile: InstitutionEducationProfile,
    *,
    configured_stage_codes: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Return a conservative standard-level plan for an eligible Uganda profile.

    Primary-only schools may safely default to P1-P7 when no campus stage has
    been configured yet. Secondary and Mixed institutions are ambiguous, so
    their plan is limited to explicitly enabled Primary/O-Level/A-Level stages.
    """
    if not _uses_uganda_national_framework(profile):
        return []

    reference = _uganda_reference_for_type(profile.institution_type)
    if not reference:
        return []

    allowed_codes = {row["code"] for row in reference}
    if configured_stage_codes is None:
        selected_codes = _configured_stage_codes(profile) & allowed_codes
    else:
        selected_codes = {str(code) for code in configured_stage_codes} & allowed_codes

    if not selected_codes:
        if profile.institution_type == InstitutionEducationProfile.PRIMARY:
            selected_codes = {EducationStage.PRIMARY}
        else:
            return []

    plan: list[dict[str, Any]] = []
    for stage in reference:
        if stage["code"] not in selected_codes:
            continue
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


def is_uganda_standard_level_quickstart_available(
    profile: InstitutionEducationProfile,
    *,
    configured_stage_codes: Iterable[str] | None = None,
) -> bool:
    return bool(
        uganda_standard_level_plan(
            profile,
            configured_stage_codes=configured_stage_codes,
        )
    )


def _classgroup_candidates_for_level(campus: Campus, level: Level):
    return ClassGroup.objects.filter(level=level).filter(
        Q(campus=campus) | Q(campus__isnull=True)
    )


def _classgroup_name_conflicts(campus: Campus, level: Level):
    return ClassGroup.objects.filter(name__iexact=level.name).filter(
        Q(campus=campus) | Q(campus__isnull=True)
    )


def _campus_stage_ids(
    profile: InstitutionEducationProfile,
    campus: Campus,
) -> set[int]:
    return set(
        CampusEducationStage.objects.filter(
            profile=profile,
            campus=campus,
            is_active=True,
        ).values_list("stage_id", flat=True)
    )


def _mapped_level_ids_for_stages(
    profile: InstitutionEducationProfile,
    stage_ids: set[int],
) -> set[int]:
    if not stage_ids:
        return set()
    return set(
        LevelStageMapping.objects.filter(
            profile=profile,
            stage_id__in=stage_ids,
        ).values_list("legacy_level_id", flat=True)
    )


def _level_is_in_campus_scope(
    profile: InstitutionEducationProfile,
    campus: Campus,
    level: Level,
) -> bool:
    """Re-check live level/stage/campus scope immediately before a write."""
    if not Level.objects.filter(pk=level.pk, is_active=True).exists():
        return False
    stage_ids = _campus_stage_ids(profile, campus)
    if not stage_ids:
        return False
    return LevelStageMapping.objects.filter(
        profile=profile,
        legacy_level_id=level.pk,
        stage_id__in=stage_ids,
    ).exists()


def class_group_quickstart_plan(
    profile: InstitutionEducationProfile,
) -> dict[str, Any]:
    """Plan one class group per in-scope active level when scope is unambiguous."""
    if profile.institution_type not in SCHOOL_CLASSGROUP_QUICKSTART_TYPES:
        return {
            "available": False,
            "reason": "institution_type",
            "message": "Higher-education and custom institutions should configure cohorts/classes explicitly.",
            "creatable": [],
        }

    campuses = list(
        Campus.objects.filter(
            organization=profile.organization,
            is_active=True,
        ).order_by("pk")[:2]
    )
    if not campuses:
        return {
            "available": False,
            "reason": "no_campus",
            "message": "Add an active campus before creating class groups.",
            "creatable": [],
        }
    if len(campuses) > 1:
        return {
            "available": False,
            "reason": "multiple_campuses",
            "message": "Choose classes per campus manually because this institution has multiple active campuses.",
            "creatable": [],
        }

    campus = campuses[0]
    stage_ids = _campus_stage_ids(profile, campus)
    if not stage_ids:
        return {
            "available": False,
            "reason": "no_enabled_stages",
            "message": "Enable and synchronize the education stages taught at this campus before creating class groups.",
            "campus": campus,
            "campus_name": campus.name,
            "creatable": [],
        }

    mapped_level_ids = _mapped_level_ids_for_stages(profile, stage_ids)
    all_active_levels = Level.objects.filter(is_active=True)
    levels = list(
        all_active_levels.filter(pk__in=mapped_level_ids).order_by("order", "name")
    )
    out_of_scope_level_names = list(
        all_active_levels.exclude(pk__in=mapped_level_ids)
        .order_by("order", "name")
        .values_list("name", flat=True)
    )
    if not levels:
        return {
            "available": False,
            "reason": "no_mapped_levels",
            "message": "No active levels are mapped to the education stages enabled for this campus. Synchronize the education structure first.",
            "campus": campus,
            "campus_name": campus.name,
            "creatable": [],
            "out_of_scope_level_names": out_of_scope_level_names,
        }

    creatable: list[dict[str, Any]] = []
    ready_level_names: list[str] = []
    inactive_level_names: list[str] = []
    conflict_level_names: list[str] = []

    for level in levels:
        existing = _classgroup_candidates_for_level(campus, level).order_by("pk").first()
        if existing is not None:
            if existing.is_active:
                ready_level_names.append(level.name)
            else:
                inactive_level_names.append(level.name)
            continue

        name_conflict = _classgroup_name_conflicts(campus, level).order_by("pk").first()
        if name_conflict is not None:
            conflict_level_names.append(level.name)
            continue

        creatable.append(
            {
                "level": level,
                "level_name": level.name,
                "class_name": level.name,
            }
        )

    return {
        "available": bool(creatable),
        "reason": "ready" if creatable else "nothing_to_create",
        "message": (
            "Create one class group for each in-scope active level that does not already have one."
            if creatable
            else "Every in-scope active level is already represented or needs administrator review."
        ),
        "campus": campus,
        "campus_name": campus.name,
        "creatable": creatable,
        "ready_level_names": ready_level_names,
        "inactive_level_names": inactive_level_names,
        "conflict_level_names": conflict_level_names,
        "out_of_scope_level_names": out_of_scope_level_names,
    }


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
            "No safe Uganda standard-level plan is available yet. Primary schools "
            "can use P1-P7 immediately. Secondary or Mixed institutions must first "
            "enable the campus stages they actually offer, such as O-Level, A-Level "
            "or Primary, so EduManage does not create levels the institution does not teach."
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


@transaction.atomic
def bootstrap_class_groups_from_levels(
    profile: InstitutionEducationProfile,
) -> dict[str, Any]:
    """Create missing single-campus school class groups without changing existing ones."""
    plan = class_group_quickstart_plan(profile)
    if not plan.get("available"):
        raise ValueError(plan.get("message") or "No safe class-group quick start is available.")

    campus = plan["campus"]
    created_names: list[str] = []
    skipped_during_create: list[str] = []
    skipped_out_of_scope: list[str] = []

    for row in plan["creatable"]:
        level = row["level"]
        if not _level_is_in_campus_scope(profile, campus, level):
            skipped_out_of_scope.append(level.name)
            continue
        if _classgroup_candidates_for_level(campus, level).exists():
            skipped_during_create.append(level.name)
            continue
        if _classgroup_name_conflicts(campus, level).exists():
            skipped_during_create.append(level.name)
            continue

        ClassGroup.objects.create(
            campus=campus,
            level=level,
            name=row["class_name"],
            code="",
            is_active=True,
        )
        created_names.append(row["class_name"])

    return {
        "campus_name": plan["campus_name"],
        "created_count": len(created_names),
        "created_names": created_names,
        "skipped_during_create": skipped_during_create,
        "skipped_out_of_scope": skipped_out_of_scope,
        "inactive_preserved": plan.get("inactive_level_names", []),
        "conflicts_preserved": plan.get("conflict_level_names", []),
        "out_of_scope_preserved": plan.get("out_of_scope_level_names", []),
    }
