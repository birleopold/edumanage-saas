"""Unified initial school setup orchestration for tenant administrators.

This module intentionally does not own academic configuration. It reads the
existing authoritative models and gives administrators one ordered setup path
across organisation settings, education frameworks, academics, assessments,
people, attendance and finance.
"""

from __future__ import annotations

from typing import Any

from django.urls import NoReverseMatch, reverse

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Level,
    ProgrammePathway,
    Stream,
    SubjectCombination,
)
from apps.tenant.assessments.models import GradingProfile, ReportRule
from apps.tenant.attendance.models import AttendancePolicy
from apps.tenant.education_frameworks.configuration import resolve_effective_terminology
from apps.tenant.education_frameworks.models import (
    CampusEducationStage,
    EducationStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.education_frameworks.services import ensure_institution_profile
from apps.tenant.finance.models import FeeItem
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import User


PROFILE_CONTACT_FIELDS = ("email", "phone", "address", "legal_name", "logo")


UGANDA_REFERENCE = (
    {
        "code": EducationStage.PRIMARY,
        "name": "Primary Education",
        "levels": ("P1", "P2", "P3", "P4", "P5", "P6", "P7"),
        "exit_exam": "PLE",
        "period": "Term",
    },
    {
        "code": EducationStage.LOWER_SECONDARY,
        "name": "Lower Secondary / O-Level",
        "levels": ("S1", "S2", "S3", "S4"),
        "exit_exam": "UCE",
        "period": "Term",
    },
    {
        "code": EducationStage.UPPER_SECONDARY,
        "name": "Upper Secondary / A-Level",
        "levels": ("S5", "S6"),
        "exit_exam": "UACE",
        "period": "Term",
    },
)


def _safe_url(name: str) -> str | None:
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def _profile_ready(org) -> bool:
    if not org or not (org.name or "").strip():
        return False
    return any(bool(getattr(org, field, None)) for field in PROFILE_CONTACT_FIELDS)


def _link(label: str, url_name: str) -> dict[str, str | None]:
    return {"label": label, "url": _safe_url(url_name)}


def _step(
    *,
    key: str,
    number: int,
    title: str,
    description: str,
    done: bool,
    evidence: list[str],
    primary_label: str,
    primary_url_name: str,
    links: list[dict[str, str | None]] | None = None,
    optional: bool = False,
    partial: bool = False,
) -> dict[str, Any]:
    if optional and not done:
        status = "optional"
    elif done:
        status = "complete"
    elif partial:
        status = "partial"
    else:
        status = "incomplete"
    return {
        "key": key,
        "number": number,
        "title": title,
        "description": description,
        "done": done,
        "optional": optional,
        "status": status,
        "evidence": evidence,
        "primary_label": primary_label,
        "primary_url": _safe_url(primary_url_name),
        "links": [row for row in (links or []) if row.get("url")],
    }


def _uganda_reference_for_type(institution_type: str) -> list[dict[str, Any]]:
    if institution_type == InstitutionEducationProfile.PRIMARY:
        allowed = {EducationStage.PRIMARY}
    elif institution_type == InstitutionEducationProfile.SECONDARY:
        allowed = {EducationStage.LOWER_SECONDARY, EducationStage.UPPER_SECONDARY}
    elif institution_type == InstitutionEducationProfile.MIXED:
        allowed = {
            EducationStage.PRIMARY,
            EducationStage.LOWER_SECONDARY,
            EducationStage.UPPER_SECONDARY,
        }
    else:
        allowed = set()
    return [dict(row) for row in UGANDA_REFERENCE if row["code"] in allowed]


def _configured_structure(profile: InstitutionEducationProfile) -> list[dict[str, Any]]:
    mappings = list(
        LevelStageMapping.objects.filter(profile=profile)
        .select_related("stage")
        .order_by("stage__order", "legacy_level_name")
    )
    levels_by_stage: dict[int, list[str]] = {}
    for mapping in mappings:
        levels_by_stage.setdefault(mapping.stage_id, []).append(
            mapping.local_name or mapping.legacy_level_name
        )

    rows = []
    for item in (
        CampusEducationStage.objects.filter(profile=profile, is_active=True)
        .select_related("campus", "stage", "framework_stage")
        .order_by("stage__order", "campus__name")
    ):
        settings = dict(getattr(item.framework_stage, "settings", None) or {})
        rows.append(
            {
                "campus": item.campus.name,
                "stage": item.local_name or item.stage.local_name or item.stage.name,
                "stage_code": item.stage.code,
                "period": item.get_academic_period_type_display(),
                "levels": levels_by_stage.get(item.stage_id, []),
                "exit_exam": settings.get("external_exam", ""),
                "assessment": item.get_default_assessment_mode_display(),
                "report": item.get_report_mode_display(),
            }
        )
    return rows


def school_setup_progress() -> dict[str, Any]:
    """Return one dependency-aware setup view over the existing school models."""
    org = get_or_create_organization()
    education_profile = ensure_institution_profile(org)
    terminology = resolve_effective_terminology(profile=education_profile)

    campus_count = Campus.objects.filter(organization=org, is_active=True).count()
    campus_stage_count = CampusEducationStage.objects.filter(
        profile=education_profile, is_active=True
    ).count()

    level_count = Level.objects.filter(is_active=True).count()
    mapped_level_count = LevelStageMapping.objects.filter(profile=education_profile).count()
    class_count = ClassGroup.objects.filter(is_active=True).count()
    stream_count = Stream.objects.filter(is_active=True).count()

    current_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = AcademicTerm.objects.filter(is_current=True).select_related("year").first()

    course_count = Course.objects.filter(is_active=True).count()
    offering_count = CourseOffering.objects.filter(is_active=True).count()
    pathway_count = ProgrammePathway.objects.filter(is_active=True).count()
    combination_count = SubjectCombination.objects.filter(is_active=True).count()

    grading_profile_count = GradingProfile.objects.filter(is_active=True).count()
    report_rule_count = ReportRule.objects.filter(grading_profile__is_active=True).count()

    teacher_count = TeacherProfile.objects.filter(is_active=True).count()
    assigned_offering_count = CourseOffering.objects.filter(
        is_active=True, teacher__isnull=False
    ).count()
    student_count = StudentProfile.objects.filter(is_active=True).count()
    fee_item_count = FeeItem.objects.filter(is_active=True).count()
    attendance_policy_count = AttendancePolicy.objects.filter(is_active=True).count()
    user_count = User.objects.filter(is_active=True).count()

    institution_ready = _profile_ready(org) and campus_count > 0
    structure_ready = bool(
        education_profile.primary_framework_id
        and campus_stage_count
        and level_count
        and mapped_level_count >= level_count
    )
    calendar_ready = bool(current_year and current_term)
    classes_ready = bool(level_count and class_count)
    subjects_ready = bool(course_count and offering_count)
    grading_ready = bool(grading_profile_count and report_rule_count)
    teaching_ready = bool(
        teacher_count
        and offering_count
        and assigned_offering_count >= offering_count
    )
    learner_ready = student_count > 0

    steps = [
        _step(
            key="institution",
            number=1,
            title="Institution profile and campuses",
            description="Identify the institution first. Everything else should inherit the school name, country and campus structure.",
            done=institution_ready,
            partial=bool(_profile_ready(org) or campus_count),
            evidence=[
                f"Institution: {org.name}",
                f"{campus_count} active campus{'es' if campus_count != 1 else ''}",
            ],
            primary_label="Institution profile",
            primary_url_name="admin_orgsettings_org",
            links=[_link("Campuses", "admin_orgsettings_campuses")],
        ),
        _step(
            key="education_structure",
            number=2,
            title="Education structure and curriculum",
            description="Choose the institution type and curriculum, then connect levels to Primary, O-Level, A-Level, tertiary or university stages.",
            done=structure_ready,
            partial=bool(education_profile.primary_framework_id or campus_stage_count or mapped_level_count),
            evidence=[
                f"Framework: {education_profile.primary_framework or 'Not selected'}",
                f"{campus_stage_count} campus stage{'s' if campus_stage_count != 1 else ''}",
                f"{mapped_level_count}/{level_count} levels mapped" if level_count else "No levels created yet",
            ],
            primary_label="Education structure",
            primary_url_name="admin_education_framework_dashboard",
            links=[
                _link("Institution & curriculum", "admin_education_framework_profile"),
                _link("School wording", "admin_education_framework_terminology"),
                _link("Levels", "admin_level_list"),
            ],
        ),
        _step(
            key="calendar",
            number=3,
            title="Academic calendar",
            description="Set the current academic year and term or semester before creating live offerings, attendance and results.",
            done=calendar_ready,
            partial=bool(current_year or AcademicTerm.objects.exists()),
            evidence=[
                f"Current year: {current_year.name}" if current_year else "No current academic year",
                f"Current period: {current_term}" if current_term else "No current term/semester",
            ],
            primary_label="Academic years",
            primary_url_name="admin_academic_year_list",
            links=[_link("Terms / semesters", "admin_academic_term_list")],
        ),
        _step(
            key="classes",
            number=4,
            title="Classes, levels and streams",
            description="Create the actual teaching groups. Streams are optional and should only be added where the institution uses them.",
            done=classes_ready,
            partial=bool(level_count or class_count),
            evidence=[
                f"{level_count} active level{'s' if level_count != 1 else ''}",
                f"{class_count} active class group{'s' if class_count != 1 else ''}",
                f"{stream_count} stream{'s' if stream_count != 1 else ''} (optional)",
            ],
            primary_label="Classes",
            primary_url_name="admin_classgroup_list",
            links=[
                _link("Levels", "admin_level_list"),
                _link("Streams", "admin_stream_list"),
                _link("Bulk stream assignment", "admin_stream_bulk_assignment"),
            ],
        ),
        _step(
            key="subjects",
            number=5,
            title="Subjects, course units and pathways",
            description="Define what is taught, then offer each subject to the correct class and period. Use pathways/combinations only where the institution needs them.",
            done=subjects_ready,
            partial=bool(course_count or offering_count),
            evidence=[
                f"{course_count} active subject/course record{'s' if course_count != 1 else ''}",
                f"{offering_count} live offering{'s' if offering_count != 1 else ''}",
                f"{pathway_count} pathway{'s' if pathway_count != 1 else ''}, {combination_count} combination{'s' if combination_count != 1 else ''} (optional)",
            ],
            primary_label="Subjects / courses",
            primary_url_name="admin_course_list",
            links=[
                _link("Subject offerings", "admin_offering_list"),
                _link("Pathways & combinations", "admin_pathway_dashboard"),
            ],
        ),
        _step(
            key="assessment",
            number=6,
            title="Assessment, grading and report rules",
            description="Configure how marks or competencies are combined, how grades are resolved and what appears on report cards.",
            done=grading_ready,
            partial=bool(grading_profile_count or report_rule_count),
            evidence=[
                f"{grading_profile_count} active grading profile{'s' if grading_profile_count != 1 else ''}",
                f"{report_rule_count} report-card rule{'s' if report_rule_count != 1 else ''}",
            ],
            primary_label="Assessment framework",
            primary_url_name="admin_assessment_framework_dashboard",
            links=[
                _link("Grading & report cards", "admin_grading_framework_dashboard"),
                _link("Grading scales", "admin_grading_scale_list"),
            ],
        ),
        _step(
            key="teaching",
            number=7,
            title="Teachers and teaching assignments",
            description="Add teachers and connect them to the subject offerings they actually teach.",
            done=teaching_ready,
            partial=bool(teacher_count or assigned_offering_count),
            evidence=[
                f"{teacher_count} active teacher{'s' if teacher_count != 1 else ''}",
                f"{assigned_offering_count}/{offering_count} offerings have teachers" if offering_count else "Create subject offerings first",
            ],
            primary_label="Teachers",
            primary_url_name="admin_teachers_list",
            links=[_link("Teaching assignments", "admin_offering_list")],
        ),
        _step(
            key="learners",
            number=8,
            title="Learners and go-live check",
            description="Add or import learners after the academic structure is ready, then confirm they are placed in the correct class/stream.",
            done=learner_ready,
            evidence=[
                f"{student_count} active learner{'s' if student_count != 1 else ''}",
                f"{user_count} active portal user{'s' if user_count != 1 else ''}",
            ],
            primary_label="Students",
            primary_url_name="admin_students_list",
            links=[_link("User access", "admin_users_list")],
        ),
    ]

    required_steps = [row for row in steps if not row["optional"]]
    completed = sum(1 for row in required_steps if row["done"])
    total = len(required_steps)
    next_step = next((row for row in steps if not row["done"] and not row["optional"]), None)

    operations = [
        _step(
            key="attendance",
            number=9,
            title="Attendance",
            description="Manual student roll call and manual staff attendance work without devices. Configure policies when reporting-time or lateness rules are needed.",
            done=attendance_policy_count > 0,
            optional=True,
            evidence=[
                f"{attendance_policy_count} attendance polic{'y' if attendance_policy_count == 1 else 'ies'}",
                "Biometric/device automation is optional",
            ],
            primary_label="Attendance setup",
            primary_url_name="admin_attendance_device_dashboard",
            links=[_link("Attendance policies", "admin_attendance_policy_list")],
        ),
        _step(
            key="finance",
            number=10,
            title="Fees and finance",
            description="Add fee items only if the institution will use EduManage billing, invoices and payment tracking.",
            done=fee_item_count > 0,
            optional=True,
            evidence=[f"{fee_item_count} active fee item{'s' if fee_item_count != 1 else ''}"],
            primary_label="Finance setup",
            primary_url_name="admin_finance_dashboard",
            links=[_link("Fee items", "admin_fee_items_list")],
        ),
    ]

    is_uganda = (
        education_profile.country_code.upper() == "UG"
        and education_profile.primary_framework
        and education_profile.primary_framework.code == "UG-NATIONAL"
    )

    return {
        "organization": org,
        "education_profile": education_profile,
        "terminology": terminology,
        "steps": steps,
        "operations": operations,
        "done_count": completed,
        "remaining_count": total - completed,
        "total": total,
        "percent": round((completed / total) * 100) if total else 100,
        "all_done": completed == total,
        "next_step": next_step,
        "configured_structure": _configured_structure(education_profile),
        "uganda_reference": _uganda_reference_for_type(education_profile.institution_type) if is_uganda else [],
        "is_uganda_framework": is_uganda,
        "advanced_links": [
            _link("Education Structure", "admin_education_framework_dashboard"),
            _link("Academic Setup", "admin_academics_setup"),
            _link("Pathways & Subject Combinations", "admin_pathway_dashboard"),
            _link("Assessment Framework", "admin_assessment_framework_dashboard"),
            _link("Grading & Report Rules", "admin_grading_framework_dashboard"),
            _link("Attendance", "admin_attendance_device_dashboard"),
            _link("Finance", "admin_finance_dashboard"),
        ],
    }
