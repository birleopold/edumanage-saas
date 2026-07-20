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
        ug_defaults = UGANDA_STAGE_SETTINGS[code]
        FrameworkStage.objects.update_or_create(
            framework=uganda,
            stage=stage,
            defaults={**ug_defaults, "is_active": True},
        )
        FrameworkStage.objects.update_or_create(
            framework=international,
            stage=stage,
            defaults={
                "local_name": stage.name,
                "class_label": "Class" if code not in {EducationStage.TERTIARY, EducationStage.UNIVERSITY} else "Year or Cohort",
                "subject_label": "Subject" if code not in {EducationStage.TERTIARY, EducationStage.UNIVERSITY} else "Course Unit",
                "period_label": "Semester" if stage.default_period_type == EducationStage.PERIOD_SEMESTER else "Academic Period",
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
    framework_code = "UG-NATIONAL" if country_code.upper() == "UG" else "INTERNATIONAL-CUSTOM"
    profile, created = InstitutionEducationProfile.objects.get_or_create(
        organization=organization,
        defaults={
            "country_code": country_code.upper(),
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


def resolve_terminology(
    *,
    profile: InstitutionEducationProfile | None = None,
    campus_stage: CampusEducationStage | None = None,
) -> dict:
    framework = profile.primary_framework if profile and profile.primary_framework_id else None
    framework_stage = campus_stage.framework_stage if campus_stage and campus_stage.framework_stage_id else None

    resolved = _merged(
        NEUTRAL_TERMINOLOGY,
        framework.default_terminology if framework else None,
        profile.terminology if profile else None,
        framework_stage.terminology if framework_stage else None,
        campus_stage.terminology if campus_stage else None,
    )
    if framework_stage:
        resolved.update(
            {
                "class": framework_stage.class_label,
                "subject": framework_stage.subject_label,
                "academic_period": framework_stage.period_label,
                "report_card": framework_stage.report_label,
            }
        )
    if campus_stage and campus_stage.local_name:
        resolved["education_stage"] = campus_stage.local_name
    elif framework_stage and framework_stage.local_name:
        resolved["education_stage"] = framework_stage.local_name
    elif campus_stage:
        resolved["education_stage"] = campus_stage.stage.name
    return resolved


def term(
    key: str,
    *,
    profile: InstitutionEducationProfile | None = None,
    campus_stage: CampusEducationStage | None = None,
    fallback: str | None = None,
) -> str:
    return str(resolve_terminology(profile=profile, campus_stage=campus_stage).get(key, fallback or key.replace("_", " ").title()))


def infer_stage_code(level_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(level_name or "").lower()).strip()

    if any(token in normalized for token in ("ecd", "nursery", "kindergarten", "pre primary", "baby class", "middle class", "top class")):
        return EducationStage.ECD
    if re.search(r"\bp\s*[1-7]\b", normalized) or "primary" in normalized or re.search(r"\bgrade\s*[1-7]\b", normalized):
        return EducationStage.PRIMARY
    if any(token in normalized for token in ("o level", "lower secondary", "junior secondary")):
        return EducationStage.LOWER_SECONDARY
    if re.search(r"\bs\s*[1-4]\b", normalized) or re.search(r"\bform\s*[1-4]\b", normalized) or re.search(r"\bgrade\s*(8|9|10)\b", normalized):
        return EducationStage.LOWER_SECONDARY
    if any(token in normalized for token in ("a level", "upper secondary", "senior secondary")):
        return EducationStage.UPPER_SECONDARY
    if re.search(r"\bs\s*[5-6]\b", normalized) or re.search(r"\bform\s*[5-6]\b", normalized) or re.search(r"\bgrade\s*(11|12|13)\b", normalized):
        return EducationStage.UPPER_SECONDARY
    if any(token in normalized for token in ("university", "bachelor", "master", "postgraduate", "degree", "doctoral", "phd")):
        return EducationStage.UNIVERSITY
    if any(token in normalized for token in ("tertiary", "tvet", "vocational", "diploma", "certificate", "technical")):
        return EducationStage.TERTIARY
    return EducationStage.OTHER


def map_existing_levels(
    profile: InstitutionEducationProfile,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    ensure_system_templates()
    Level = apps.get_model("academics", "Level")
    summary = {"created": 0, "updated": 0, "unchanged": 0}

    for level in Level.objects.all().order_by("order", "name"):
        stage = EducationStage.objects.get(code=infer_stage_code(level.name))
        existing = LevelStageMapping.objects.filter(
            profile=profile,
            legacy_level_id=level.pk,
        ).first()
        if existing and existing.stage_id == stage.pk and existing.legacy_level_name == level.name:
            summary["unchanged"] += 1
            continue
        if dry_run:
            summary["updated" if existing else "created"] += 1
            continue
        _, created = LevelStageMapping.objects.update_or_create(
            profile=profile,
            legacy_level_id=level.pk,
            defaults={
                "legacy_level_name": level.name,
                "local_name": level.name,
                "stage": stage,
            },
        )
        summary["created" if created else "updated"] += 1
    return summary


def enable_mapped_stages(profile: InstitutionEducationProfile) -> int:
    framework = profile.primary_framework
    if not framework:
        return 0
    stage_ids = profile.level_mappings.values_list("stage_id", flat=True).distinct()
    created_count = 0
    for campus in profile.organization.campuses.filter(is_active=True):
        for stage in EducationStage.objects.filter(pk__in=stage_ids, is_active=True):
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
                    "local_name": framework_stage.local_name if framework_stage else stage.local_name,
                    "academic_period_type": stage.default_period_type,
                },
            )
            created_count += int(created)
    return created_count


def resolve_level_stage(level, profile: InstitutionEducationProfile) -> EducationStage:
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
    return GradingScale.objects.filter(pk=campus_stage.grading_scale_id).first()
