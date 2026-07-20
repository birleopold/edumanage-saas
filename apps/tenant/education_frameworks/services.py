from __future__ import annotations

import re
from collections.abc import Mapping

from django.apps import apps

from apps.tenant.orgsettings.models import OrganizationProfile

from .models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)


NEUTRAL_TERMINOLOGY = {
    "institution": "Institution",
    "school": "School",
    "learner": "Student",
    "guardian": "Parent or Guardian",
    "teacher": "Teacher",
    "class": "Class",
    "stream": "Stream",
    "subject": "Subject",
    "course": "Course",
    "course_unit": "Course Unit",
    "academic_period": "Academic Period",
    "term": "Term",
    "semester": "Semester",
    "assessment": "Assessment",
    "exam": "Exam",
    "coursework": "Coursework",
    "assignment": "Assignment",
    "report_card": "Report Card",
    "candidate": "Candidate",
    "external_exam": "External Exam",
    "boarding": "Boarding and Welfare",
    "hostel": "Hostel or Residence",
    "house": "House",
    "fees": "Fees",
    "clearance": "Assessment Clearance",
    "activities": "Clubs, Sports and Activities",
}

UGANDA_TERMINOLOGY = {
    **NEUTRAL_TERMINOLOGY,
    "institution": "School or Institution",
    "learner": "Learner",
    "guardian": "Parent or Guardian",
    "external_exam": "UNEB or External Exam",
    "boarding": "Boarding and Student Welfare",
    "clearance": "Exam and Fees Clearance",
}

MAPPING_SOURCE_AUTO = "AUTO"
MAPPING_SOURCE_MANUAL = "MANUAL"


STAGE_TEMPLATES = (
    {
        "code": EducationStage.ECD,
        "name": "Early Childhood Education",
        "local_name": "ECD / Pre-Primary",
        "order": 10,
        "default_period_type": EducationStage.PERIOD_TERM,
        "description": "Nursery, kindergarten, pre-primary and early-years programmes.",
    },
    {
        "code": EducationStage.PRIMARY,
        "name": "Primary Education",
        "local_name": "Primary",
        "order": 20,
        "default_period_type": EducationStage.PERIOD_TERM,
        "description": "Primary or elementary education levels.",
    },
    {
        "code": EducationStage.LOWER_SECONDARY,
        "name": "Lower Secondary Education",
        "local_name": "O-Level / Lower Secondary",
        "order": 30,
        "default_period_type": EducationStage.PERIOD_TERM,
        "description": "Lower-secondary programmes, including Uganda O-Level.",
    },
    {
        "code": EducationStage.UPPER_SECONDARY,
        "name": "Upper Secondary Education",
        "local_name": "A-Level / Upper Secondary",
        "order": 40,
        "default_period_type": EducationStage.PERIOD_TERM,
        "description": "Upper-secondary programmes, including Uganda A-Level.",
    },
    {
        "code": EducationStage.TERTIARY,
        "name": "Tertiary and Vocational Education",
        "local_name": "Tertiary / TVET",
        "order": 50,
        "default_period_type": EducationStage.PERIOD_SEMESTER,
        "description": "Certificate, diploma, vocational and technical programmes.",
    },
    {
        "code": EducationStage.UNIVERSITY,
        "name": "University Education",
        "local_name": "University",
        "order": 60,
        "default_period_type": EducationStage.PERIOD_SEMESTER,
        "description": "Undergraduate, postgraduate and university programmes.",
    },
    {
        "code": EducationStage.OTHER,
        "name": "Other Education Programme",
        "local_name": "Other / Custom",
        "order": 90,
        "default_period_type": EducationStage.PERIOD_CUSTOM,
        "description": "Flexible stage for programmes outside the standard templates.",
    },
)


FRAMEWORK_TEMPLATES = (
    {
        "code": "UG-NATIONAL",
        "name": "Uganda National Curriculum",
        "country_code": "UG",
        "description": "Configurable Uganda-oriented template with international-neutral core labels.",
        "default_terminology": UGANDA_TERMINOLOGY,
        "default_settings": {
            "assessment_aliases": {
                "BOT": "Beginning of Term Test",
                "MOT": "Mid-Term Test",
                "EOT": "End of Term Examination",
                "AOI": "Activity of Integration",
            },
            "external_exam_aliases": ["PLE", "UCE", "UACE", "UNEB"],
            "performing_arts_alias": "MDD",
        },
    },
    {
        "code": "INTERNATIONAL-CUSTOM",
        "name": "International or Custom Curriculum",
        "country_code": "",
        "description": "Neutral template for international, private and custom curricula.",
        "default_terminology": NEUTRAL_TERMINOLOGY,
        "default_settings": {},
    },
)


UGANDA_STAGE_SETTINGS = {
    EducationStage.ECD: {
        "local_name": "ECD / Pre-Primary",
        "class_label": "Class",
        "subject_label": "Learning Area",
        "period_label": "Term",
        "report_label": "Progress Report",
        "candidate_class": False,
    },
    EducationStage.PRIMARY: {
        "local_name": "Primary",
        "class_label": "Class",
        "subject_label": "Subject",
        "period_label": "Term",
        "report_label": "Report Card",
        "candidate_class": True,
        "settings": {"candidate_levels": ["P7"], "external_exam": "PLE"},
    },
    EducationStage.LOWER_SECONDARY: {
        "local_name": "O-Level / Lower Secondary",
        "class_label": "Class",
        "subject_label": "Subject",
        "period_label": "Term",
        "report_label": "Report Card",
        "candidate_class": True,
        "settings": {"candidate_levels": ["S4"], "external_exam": "UCE"},
    },
    EducationStage.UPPER_SECONDARY: {
        "local_name": "A-Level / Upper Secondary",
        "class_label": "Class",
        "subject_label": "Subject",
        "period_label": "Term",
        "report_label": "Report Card",
        "candidate_class": True,
        "settings": {"candidate_levels": ["S6"], "external_exam": "UACE"},
    },
    EducationStage.TERTIARY: {
        "local_name": "Tertiary / TVET",
        "class_label": "Year or Cohort",
        "subject_label": "Course Unit",
        "period_label": "Semester",
        "report_label": "Academic Report",
        "candidate_class": False,
    },
    EducationStage.UNIVERSITY: {
        "local_name": "University",
        "class_label": "Year or Cohort",
        "subject_label": "Course Unit",
        "period_label": "Semester",
        "report_label": "Academic Transcript",
        "candidate_class": False,
    },
    EducationStage.OTHER: {
        "local_name": "Other / Custom",
        "class_label": "Group",
        "subject_label": "Course",
        "period_label": "Academic Period",
        "report_label": "Academic Report",
        "candidate_class": False,
    },
}


def _merged(*values: Mapping | None) -> dict:
    result: dict = {}
    for value in values:
        if value:
            result.update(dict(value))
    return result


def ensure_system_templates() -> tuple[dict[str, EducationStage], dict[str, AcademicFramework]]:
    stages: dict[str, EducationStage] = {}
    for template in STAGE_TEMPLATES:
        code = template["code"]
        defaults = {key: value for key, value in template.items() if key != "code"}
        stage, _ = EducationStage.objects.update_or_create(
            code=code,
            defaults={**defaults, "is_system": True, "is_active": True},
        )
        stages[code] = stage

    frameworks: dict[str, AcademicFramework] = {}
    for template in FRAMEWORK_TEMPLATES:
        code = template["code"]
        defaults = {key: value for key, value in template.items() if key != "code"}
        framework, _ = AcademicFramework.objects.update_or_create(
            code=code,
            defaults={**defaults, "is_system_template": True, "is_active": True},
        )
        frameworks[code] = framework

    uganda = frameworks["UG-NATIONAL"]
    international = frameworks["INTERNATIONAL-CUSTOM"]
    for code, stage in stages.items():
        FrameworkStage.objects.update_or_create(
            framework=uganda,
            stage=stage,
            defaults={**UGANDA_STAGE_SETTINGS[code], "is_active": True},
        )
        higher_education = code in {
            EducationStage.TERTIARY,
            EducationStage.UNIVERSITY,
        }
        FrameworkStage.objects.update_or_create(
            framework=international,
            stage=stage,
            defaults={
                "local_name": stage.name,
                "class_label": "Year or Cohort" if higher_education else "Class",
                "subject_label": "Course Unit" if higher_education else "Subject",
                "period_label": (
                    "Semester"
                    if stage.default_period_type == EducationStage.PERIOD_SEMESTER
                    else "Academic Period"
                ),
                "report_label": "Academic Report",
                "candidate_class": False,
                "is_active": True,
            },
        )

    return stages, frameworks


def ensure_institution_profile(
    organization: OrganizationProfile,
    *,
    country_code: str = "UG",
    locale: str = "en-UG",
    institution_type: str = InstitutionEducationProfile.MIXED,
) -> InstitutionEducationProfile:
    _, frameworks = ensure_system_templates()
    normalized_country = country_code.upper()
    framework_code = (
        "UG-NATIONAL"
        if normalized_country == "UG"
        else "INTERNATIONAL-CUSTOM"
    )
    profile, created = InstitutionEducationProfile.objects.get_or_create(
        organization=organization,
        defaults={
            "country_code": normalized_country,
            "locale": locale,
            "institution_type": institution_type,
            "primary_framework": frameworks[framework_code],
            "terminology": {},
        },
    )
    if not created and not profile.primary_framework_id:
        profile.primary_framework = frameworks[framework_code]
        profile.save(update_fields=["primary_framework", "updated_at"])
    return profile


def _neutral_stage_labels(campus_stage: CampusEducationStage) -> dict[str, str]:
    higher_education = campus_stage.stage.code in {
        EducationStage.TERTIARY,
        EducationStage.UNIVERSITY,
    }
    if campus_stage.academic_period_type == EducationStage.PERIOD_SEMESTER:
        period_label = "Semester"
    elif campus_stage.academic_period_type == EducationStage.PERIOD_TERM:
        period_label = "Term"
    elif campus_stage.academic_period_type == EducationStage.PERIOD_YEAR:
        period_label = "Academic Year"
    else:
        period_label = "Academic Period"
    return {
        "education_stage": campus_stage.stage.name,
        "class": "Year or Cohort" if higher_education else "Class",
        "subject": "Course Unit" if higher_education else "Subject",
        "academic_period": period_label,
        "report_card": "Academic Report" if higher_education else "Report Card",
    }


def resolve_terminology(
    *,
    profile: InstitutionEducationProfile | None = None,
    campus_stage: CampusEducationStage | None = None,
) -> dict[str, str]:
    """Resolve labels from broad defaults to the most specific explicit override.

    Precedence is neutral defaults, selected framework, framework-stage defaults,
    institution overrides, campus-stage display name and campus-stage overrides.
    When local terminology is disabled, framework-specific labels are skipped.
    """

    use_local = bool(profile is None or profile.use_local_terminology)
    framework = (
        profile.primary_framework
        if use_local and profile and profile.primary_framework_id
        else None
    )
    framework_stage = (
        campus_stage.framework_stage
        if use_local and campus_stage and campus_stage.framework_stage_id
        else None
    )

    stage_labels: dict[str, str] = {}
    if campus_stage:
        if framework_stage:
            stage_labels.update(
                {
                    "education_stage": (
                        framework_stage.local_name or campus_stage.stage.name
                    ),
                    "class": framework_stage.class_label,
                    "subject": framework_stage.subject_label,
                    "academic_period": framework_stage.period_label,
                    "report_card": framework_stage.report_label,
                }
            )
        else:
            stage_labels.update(_neutral_stage_labels(campus_stage))

    resolved = _merged(
        NEUTRAL_TERMINOLOGY,
        framework.default_terminology if framework else None,
        framework_stage.terminology if framework_stage else None,
        stage_labels,
        profile.terminology if profile else None,
    )
    if campus_stage and campus_stage.local_name:
        resolved["education_stage"] = campus_stage.local_name
    if campus_stage:
        resolved.update(dict(campus_stage.terminology or {}))
    return {str(key): str(value) for key, value in resolved.items()}


def term(
    key: str,
    *,
    profile: InstitutionEducationProfile | None = None,
    campus_stage: CampusEducationStage | None = None,
    fallback: str | None = None,
) -> str:
    labels = resolve_terminology(profile=profile, campus_stage=campus_stage)
    return str(labels.get(key, fallback or key.replace("_", " ").title()))


def infer_stage_code(level_name: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(level_name or "").lower(),
    ).strip()

    if any(
        token in normalized
        for token in (
            "ecd",
            "nursery",
            "kindergarten",
            "pre primary",
            "baby class",
            "middle class",
            "top class",
        )
    ):
        return EducationStage.ECD
    if (
        re.search(r"\bp\s*[1-7]\b", normalized)
        or "primary" in normalized
        or re.search(r"\bgrade\s*[1-7]\b", normalized)
    ):
        return EducationStage.PRIMARY
    if any(
        token in normalized
        for token in ("o level", "lower secondary", "junior secondary")
    ):
        return EducationStage.LOWER_SECONDARY
    if (
        re.search(r"\bs\s*[1-4]\b", normalized)
        or re.search(r"\bform\s*[1-4]\b", normalized)
        or re.search(r"\bgrade\s*(8|9|10)\b", normalized)
    ):
        return EducationStage.LOWER_SECONDARY
    if any(
        token in normalized
        for token in ("a level", "upper secondary", "senior secondary")
    ):
        return EducationStage.UPPER_SECONDARY
    if (
        re.search(r"\bs\s*[5-6]\b", normalized)
        or re.search(r"\bform\s*[5-6]\b", normalized)
        or re.search(r"\bgrade\s*(11|12|13)\b", normalized)
    ):
        return EducationStage.UPPER_SECONDARY
    if any(
        token in normalized
        for token in (
            "university",
            "bachelor",
            "master",
            "postgraduate",
            "degree",
            "doctoral",
            "phd",
        )
    ):
        return EducationStage.UNIVERSITY
    if any(
        token in normalized
        for token in (
            "tertiary",
            "tvet",
            "vocational",
            "diploma",
            "certificate",
            "technical",
        )
    ):
        return EducationStage.TERTIARY
    return EducationStage.OTHER


def _mapping_settings(mapping: LevelStageMapping | None) -> dict:
    return dict(mapping.settings or {}) if mapping else {}


def map_existing_levels(
    profile: InstitutionEducationProfile,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Map legacy levels while preserving administrator-confirmed corrections."""

    ensure_system_templates()
    Level = apps.get_model("academics", "Level")
    summary = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "manual_preserved": 0,
    }

    for level in Level.objects.all().order_by("order", "name"):
        inferred_stage = EducationStage.objects.get(
            code=infer_stage_code(level.name)
        )
        existing = LevelStageMapping.objects.filter(
            profile=profile,
            legacy_level_id=level.pk,
        ).first()
        existing_settings = _mapping_settings(existing)
        is_manual = (
            existing_settings.get("source") == MAPPING_SOURCE_MANUAL
        )

        if existing and is_manual:
            if existing.legacy_level_name == level.name:
                summary["unchanged"] += 1
                summary["manual_preserved"] += 1
                continue
            if dry_run:
                summary["updated"] += 1
                summary["manual_preserved"] += 1
                continue
            existing.legacy_level_name = level.name
            existing.settings = {
                **existing_settings,
                "source": MAPPING_SOURCE_MANUAL,
                "last_seen_name": level.name,
            }
            existing.save(
                update_fields=[
                    "legacy_level_name",
                    "settings",
                    "updated_at",
                ]
            )
            summary["updated"] += 1
            summary["manual_preserved"] += 1
            continue

        if (
            existing
            and existing.stage_id == inferred_stage.pk
            and existing.legacy_level_name == level.name
        ):
            summary["unchanged"] += 1
            continue

        if dry_run:
            summary["updated" if existing else "created"] += 1
            continue

        auto_settings = {
            **existing_settings,
            "source": MAPPING_SOURCE_AUTO,
            "inferred_from_name": level.name,
        }
        _, created = LevelStageMapping.objects.update_or_create(
            profile=profile,
            legacy_level_id=level.pk,
            defaults={
                "legacy_level_name": level.name,
                "local_name": level.name,
                "stage": inferred_stage,
                "settings": auto_settings,
            },
        )
        summary["created" if created else "updated"] += 1
    return summary


def enable_mapped_stages(profile: InstitutionEducationProfile) -> int:
    framework = profile.primary_framework
    if not framework:
        return 0
    stage_ids = profile.level_mappings.values_list(
        "stage_id",
        flat=True,
    ).distinct()
    created_count = 0
    for campus in profile.organization.campuses.filter(is_active=True):
        for stage in EducationStage.objects.filter(
            pk__in=stage_ids,
            is_active=True,
        ):
            framework_stage = FrameworkStage.objects.filter(
                framework=framework,
                stage=stage,
                is_active=True,
            ).first()
            _, created = CampusEducationStage.objects.get_or_create(
                profile=profile,
                campus=campus,
                stage=stage,
                defaults={
                    "framework_stage": framework_stage,
                    "local_name": (
                        framework_stage.local_name
                        if framework_stage
                        else stage.local_name
                    ),
                    "academic_period_type": stage.default_period_type,
                },
            )
            created_count += int(created)
    return created_count


def resolve_level_stage(
    level,
    profile: InstitutionEducationProfile,
) -> EducationStage:
    mapping = LevelStageMapping.objects.filter(
        profile=profile,
        legacy_level_id=level.pk,
    ).select_related("stage").first()
    if mapping:
        return mapping.stage
    return EducationStage.objects.get(code=infer_stage_code(level.name))


def resolve_grading_scale(campus_stage: CampusEducationStage):
    if not campus_stage.grading_scale_id:
        return None
    GradingScale = apps.get_model("academics", "GradingScale")
    return GradingScale.objects.filter(
        pk=campus_stage.grading_scale_id
    ).first()
