from __future__ import annotations

from django.apps import apps
from django.db.models import F

from .models import CampusEducationStage, FrameworkStage, InstitutionEducationProfile
from .services import resolve_terminology


def resolve_effective_terminology(
    *,
    profile: InstitutionEducationProfile,
    campus_stage: CampusEducationStage | None = None,
) -> dict[str, str]:
    """Backward-compatible entry point for the canonical terminology resolver."""

    return resolve_terminology(profile=profile, campus_stage=campus_stage)


def sync_framework_stage_links(profile: InstitutionEducationProfile) -> dict[str, int]:
    """Relink campus stages after a framework change without replacing local settings."""

    summary = {"updated": 0, "cleared": 0, "unchanged": 0, "unsupported": 0}
    for campus_stage in profile.campus_stages.select_related("stage", "framework_stage"):
        framework_stage = FrameworkStage.objects.filter(
            framework=profile.primary_framework,
            stage=campus_stage.stage,
            is_active=True,
        ).first()
        if framework_stage is None:
            summary["unsupported"] += 1
            if campus_stage.framework_stage_id is not None:
                campus_stage.framework_stage = None
                campus_stage.full_clean()
                campus_stage.save(update_fields=["framework_stage", "updated_at"])
                summary["cleared"] += 1
            else:
                summary["unchanged"] += 1
            continue
        if campus_stage.framework_stage_id == framework_stage.pk:
            summary["unchanged"] += 1
            continue
        campus_stage.framework_stage = framework_stage
        if not campus_stage.local_name:
            campus_stage.local_name = framework_stage.local_name
        campus_stage.full_clean()
        campus_stage.save(
            update_fields=["framework_stage", "local_name", "updated_at"]
        )
        summary["updated"] += 1
    return summary


def framework_readiness(profile: InstitutionEducationProfile) -> dict:
    """Return a non-mutating setup summary for administrators and rollout checks."""

    Level = apps.get_model("academics", "Level")
    GradingScale = apps.get_model("academics", "GradingScale")

    level_count = Level.objects.count()
    mapped_level_ids = set(
        profile.level_mappings.values_list("legacy_level_id", flat=True)
    )
    existing_level_ids = set(Level.objects.values_list("id", flat=True))
    orphaned_mappings = len(mapped_level_ids - existing_level_ids)
    unmapped_levels = level_count - len(mapped_level_ids & existing_level_ids)
    expected_stage_ids = set(
        profile.level_mappings.filter(
            legacy_level_id__in=existing_level_ids
        ).values_list("stage_id", flat=True)
    )

    active_campuses = list(
        profile.organization.campuses.filter(is_active=True).only("id")
    )
    campus_count = len(active_campuses)
    campus_stages = profile.campus_stages.filter(is_active=True)
    configured_pairs = set(
        campus_stages.values_list("campus_id", "stage_id")
    )
    missing_campus_stage_count = 0
    configured_campuses = 0
    for campus in active_campuses:
        campus_stage_ids = {
            stage_id
            for campus_id, stage_id in configured_pairs
            if campus_id == campus.id
        }
        missing = expected_stage_ids - campus_stage_ids
        missing_campus_stage_count += len(missing)
        if not missing:
            configured_campuses += 1

    grading_configured = campus_stages.exclude(
        grading_scale_id__isnull=True
    ).count()
    valid_grading_ids = set(
        GradingScale.objects.values_list("id", flat=True)
    )
    invalid_grading_links = sum(
        1
        for grading_scale_id in campus_stages.exclude(
            grading_scale_id__isnull=True
        ).values_list("grading_scale_id", flat=True)
        if grading_scale_id not in valid_grading_ids
    )

    framework_mismatches = campus_stages.filter(
        framework_stage__isnull=False,
    ).exclude(
        framework_stage__framework_id=profile.primary_framework_id,
    ).count()
    stage_mismatches = campus_stages.filter(
        framework_stage__isnull=False,
    ).exclude(
        framework_stage__stage_id=F("stage_id"),
    ).count()
    unsupported_stage_links = (
        campus_stages.filter(framework_stage__isnull=True).count()
        if profile.primary_framework_id
        else 0
    )

    checks = {
        "profile_active": profile.is_active,
        "framework_selected": bool(profile.primary_framework_id),
        "campuses_configured": missing_campus_stage_count == 0,
        "levels_mapped": unmapped_levels == 0,
        "no_orphaned_mappings": orphaned_mappings == 0,
        "grading_links_valid": invalid_grading_links == 0,
        "framework_links_valid": framework_mismatches == 0,
        "stage_links_valid": stage_mismatches == 0,
        "stages_supported": unsupported_stage_links == 0,
    }
    completed = sum(bool(value) for value in checks.values())

    return {
        "checks": checks,
        "completed_checks": completed,
        "total_checks": len(checks),
        "completion_percent": round((completed / len(checks)) * 100) if checks else 100,
        "campus_count": campus_count,
        "configured_campuses": configured_campuses,
        "campus_stage_count": campus_stages.count(),
        "missing_campus_stage_count": missing_campus_stage_count,
        "level_count": level_count,
        "mapped_level_count": len(mapped_level_ids & existing_level_ids),
        "unmapped_level_count": max(unmapped_levels, 0),
        "orphaned_mapping_count": orphaned_mappings,
        "grading_configured_count": grading_configured,
        "invalid_grading_link_count": invalid_grading_links,
        "framework_mismatch_count": framework_mismatches,
        "stage_mismatch_count": stage_mismatches,
        "unsupported_stage_link_count": unsupported_stage_links,
    }
