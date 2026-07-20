from __future__ import annotations

from django.apps import apps

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

    campus_count = profile.organization.campuses.filter(is_active=True).count()
    campus_stages = profile.campus_stages.filter(is_active=True)
    configured_campuses = campus_stages.values("campus_id").distinct().count()
    grading_configured = campus_stages.exclude(grading_scale_id__isnull=True).count()
    invalid_grading_links = 0
    valid_grading_ids = set(GradingScale.objects.values_list("id", flat=True))
    for grading_scale_id in campus_stages.exclude(
        grading_scale_id__isnull=True
    ).values_list("grading_scale_id", flat=True):
        if grading_scale_id not in valid_grading_ids:
            invalid_grading_links += 1

    checks = {
        "profile_active": profile.is_active,
        "framework_selected": bool(profile.primary_framework_id),
        "campuses_configured": campus_count == 0 or configured_campuses == campus_count,
        "levels_mapped": unmapped_levels == 0,
        "no_orphaned_mappings": orphaned_mappings == 0,
        "grading_links_valid": invalid_grading_links == 0,
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
        "level_count": level_count,
        "mapped_level_count": len(mapped_level_ids & existing_level_ids),
        "unmapped_level_count": max(unmapped_levels, 0),
        "orphaned_mapping_count": orphaned_mappings,
        "grading_configured_count": grading_configured,
        "invalid_grading_link_count": invalid_grading_links,
    }
