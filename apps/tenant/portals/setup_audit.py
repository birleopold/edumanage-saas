"""Read-only validity audit for the School Setup Center.

The setup center used to treat the presence of records as proof that a stage was
ready.  This module verifies that the records agree with one another and
returns plain-language blockers/warnings for non-technical administrators.
It never mutates school data.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q
from django.utils import timezone

from apps.tenant.academics.models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    GradeRange,
    Level,
    Stream,
)
from apps.tenant.assessments.models import GradingProfile, ReportRule
from apps.tenant.attendance.models import AttendancePolicy
from apps.tenant.education_frameworks.models import (
    CampusEducationStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.finance.models import FeeItem
from apps.tenant.orgsettings.models import Campus
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile


SCHOOL_TYPES = {
    InstitutionEducationProfile.ECD,
    InstitutionEducationProfile.PRIMARY,
    InstitutionEducationProfile.SECONDARY,
    InstitutionEducationProfile.MIXED,
}


def _finding(
    code: str,
    title: str,
    message: str,
    *,
    action_label: str,
    action_url_name: str,
) -> dict[str, str]:
    return {
        "code": code,
        "title": title,
        "message": message,
        "action_label": action_label,
        "action_url_name": action_url_name,
    }


def _result(blockers=None, warnings=None, **metrics) -> dict[str, Any]:
    blockers = list(blockers or [])
    warnings = list(warnings or [])
    return {
        "valid": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "metrics": metrics,
    }


def _institution_audit(org, active_campuses: list[Campus]) -> dict[str, Any]:
    blockers = []
    warnings = []

    if not (getattr(org, "name", "") or "").strip():
        blockers.append(
            _finding(
                "institution_name_missing",
                "Enter the institution name",
                "EduManage needs the official school/institution name before reports and records can be identified correctly.",
                action_label="Edit institution profile",
                action_url_name="admin_orgsettings_org",
            )
        )
    if not active_campuses:
        blockers.append(
            _finding(
                "campus_missing",
                "Add at least one campus",
                "Classes, staff, learners and education stages need an active campus scope.",
                action_label="Manage campuses",
                action_url_name="admin_orgsettings_campuses",
            )
        )

    active_default_count = sum(1 for campus in active_campuses if campus.is_default)
    if active_default_count > 1:
        blockers.append(
            _finding(
                "multiple_default_campuses",
                "More than one campus is marked as default",
                "Choose one default campus so new records do not inherit an ambiguous campus.",
                action_label="Review campuses",
                action_url_name="admin_orgsettings_campuses",
            )
        )
    elif len(active_campuses) > 1 and active_default_count == 0:
        warnings.append(
            _finding(
                "default_campus_missing",
                "Choose a default campus",
                "This is a multi-campus institution. A default campus makes initial data entry clearer, while users can still choose another campus when needed.",
                action_label="Review campuses",
                action_url_name="admin_orgsettings_campuses",
            )
        )

    if not any((getattr(org, field, "") or "").strip() for field in ("email", "phone", "address")):
        warnings.append(
            _finding(
                "institution_contact_missing",
                "Add a contact detail",
                "Add an email, phone number or address so official documents and administrators have a clear school contact.",
                action_label="Edit institution profile",
                action_url_name="admin_orgsettings_org",
            )
        )

    return _result(
        blockers,
        warnings,
        active_campus_count=len(active_campuses),
        default_campus_count=active_default_count,
    )


def _education_structure_audit(org, profile, active_campuses: list[Campus]) -> dict[str, Any]:
    blockers = []
    warnings = []
    active_levels = list(Level.objects.filter(is_active=True).order_by("order", "name"))
    all_level_ids = set(Level.objects.values_list("id", flat=True))
    active_level_ids = {level.pk for level in active_levels}

    framework = profile.primary_framework
    if framework is None:
        blockers.append(
            _finding(
                "framework_missing",
                "Choose the curriculum/framework",
                "EduManage cannot interpret levels, assessment wording or education stages until a framework is selected.",
                action_label="Choose institution & curriculum",
                action_url_name="admin_education_framework_profile",
            )
        )
    elif not framework.is_active:
        blockers.append(
            _finding(
                "framework_inactive",
                "The selected curriculum is inactive",
                "Choose an active curriculum/framework before continuing.",
                action_label="Choose institution & curriculum",
                action_url_name="admin_education_framework_profile",
            )
        )
    elif framework.country_code and profile.country_code and framework.country_code.upper() != profile.country_code.upper():
        warnings.append(
            _finding(
                "framework_country_mismatch",
                "Check the curriculum country",
                f"The institution country is {profile.country_code.upper()}, but the selected framework is marked {framework.country_code.upper()}.",
                action_label="Review institution & curriculum",
                action_url_name="admin_education_framework_profile",
            )
        )

    active_stage_qs = CampusEducationStage.objects.filter(profile=profile, is_active=True).select_related(
        "campus", "stage", "framework_stage"
    )
    active_stages = list(active_stage_qs)
    active_campus_ids = {campus.pk for campus in active_campuses}
    stage_campus_ids = {row.campus_id for row in active_stages if row.campus_id in active_campus_ids}
    missing_campuses = [campus.name for campus in active_campuses if campus.pk not in stage_campus_ids]
    if missing_campuses:
        blockers.append(
            _finding(
                "campus_stage_missing",
                "Choose education stages for every campus",
                "No education stage is enabled for: " + ", ".join(missing_campuses) + ".",
                action_label="Configure education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    inactive_campus_stage_count = active_stage_qs.filter(campus__is_active=False).count()
    if inactive_campus_stage_count:
        blockers.append(
            _finding(
                "stage_on_inactive_campus",
                "Education stages are attached to an inactive campus",
                f"{inactive_campus_stage_count} active education-stage record(s) belong to an inactive campus. Disable or move them before relying on the structure.",
                action_label="Configure education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    inactive_stage_count = active_stage_qs.filter(stage__is_active=False).count()
    if inactive_stage_count:
        blockers.append(
            _finding(
                "inactive_stage_enabled",
                "An inactive education stage is still enabled",
                f"{inactive_stage_count} campus stage(s) point to an education stage that has been disabled.",
                action_label="Configure education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    if not active_levels:
        blockers.append(
            _finding(
                "levels_missing",
                "Create academic levels",
                "Add the levels used by the institution, such as P1, S1, Year 1 or another local equivalent.",
                action_label="Manage levels",
                action_url_name="admin_level_list",
            )
        )

    mappings = list(LevelStageMapping.objects.filter(profile=profile).select_related("stage"))
    mapping_by_level_id = {row.legacy_level_id: row for row in mappings}
    unmapped = [level.name for level in active_levels if level.pk not in mapping_by_level_id]
    if unmapped:
        blockers.append(
            _finding(
                "active_levels_unmapped",
                "Some active levels are not connected to an education stage",
                "Map these levels before continuing: " + ", ".join(unmapped[:12]) + ("…" if len(unmapped) > 12 else "") + ".",
                action_label="Synchronize education structure",
                action_url_name="admin_school_setup_guide",
            )
        )

    active_mappings = [row for row in mappings if row.legacy_level_id in active_level_ids]
    inactive_mapping_stage_names = sorted({row.legacy_level_name for row in active_mappings if not row.stage.is_active})
    if inactive_mapping_stage_names:
        blockers.append(
            _finding(
                "mapping_to_inactive_stage",
                "A level is mapped to an inactive education stage",
                "Review: " + ", ".join(inactive_mapping_stage_names[:12]) + ".",
                action_label="Configure education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    enabled_stage_ids = {
        row.stage_id
        for row in active_stages
        if row.campus_id in active_campus_ids and row.stage.is_active
    }
    outside_enabled = sorted(
        {
            row.legacy_level_name
            for row in active_mappings
            if row.stage_id not in enabled_stage_ids
        }
    )
    if outside_enabled:
        blockers.append(
            _finding(
                "mapped_stage_not_enabled",
                "Some mapped levels belong to stages no campus offers",
                "Enable the matching campus stage or correct these level mappings: "
                + ", ".join(outside_enabled[:12])
                + ("…" if len(outside_enabled) > 12 else "")
                + ".",
                action_label="Configure education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    stale_mapping_count = sum(1 for row in mappings if row.legacy_level_id not in all_level_ids)
    inactive_level_mapping_count = sum(
        1
        for row in mappings
        if row.legacy_level_id in all_level_ids and row.legacy_level_id not in active_level_ids
    )
    if stale_mapping_count or inactive_level_mapping_count:
        warnings.append(
            _finding(
                "stale_level_mappings",
                "Old level mappings need review",
                f"Found {stale_mapping_count} mapping(s) whose level no longer exists and {inactive_level_mapping_count} mapping(s) for inactive levels. They do not count as active setup.",
                action_label="Review education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    if framework is not None:
        wrong_framework_count = active_stage_qs.exclude(framework_stage__isnull=True).exclude(
            framework_stage__framework_id=framework.pk
        ).count()
        wrong_stage_link_count = active_stage_qs.exclude(framework_stage__isnull=True).exclude(
            framework_stage__stage_id=F("stage_id")
        ).count()
        if wrong_framework_count or wrong_stage_link_count:
            blockers.append(
                _finding(
                    "framework_stage_mismatch",
                    "A campus stage is linked to the wrong curriculum setting",
                    "Synchronize the education structure so each campus stage uses the selected curriculum and matching stage.",
                    action_label="Synchronize education structure",
                    action_url_name="admin_school_setup_guide",
                )
            )
        missing_framework_links = active_stage_qs.filter(framework_stage__isnull=True).count()
        if missing_framework_links:
            warnings.append(
                _finding(
                    "framework_stage_link_missing",
                    "Some curriculum links can be refreshed",
                    f"{missing_framework_links} campus stage(s) have no framework-stage link. Synchronizing can restore curriculum labels and defaults without replacing manual mappings.",
                    action_label="Synchronize education structure",
                    action_url_name="admin_school_setup_guide",
                )
            )

    return _result(
        blockers,
        warnings,
        active_level_count=len(active_levels),
        mapped_active_level_count=len(active_mappings),
        campus_stage_count=len([row for row in active_stages if row.campus_id in active_campus_ids]),
        enabled_stage_ids=sorted(enabled_stage_ids),
    )


def _calendar_audit(profile) -> dict[str, Any]:
    blockers = []
    warnings = []
    current_years = list(AcademicYear.objects.filter(is_current=True).order_by("pk")[:3])
    current_terms = list(AcademicTerm.objects.filter(is_current=True).select_related("year").order_by("pk")[:3])

    if not current_years:
        blockers.append(
            _finding(
                "current_year_missing",
                "Choose the current academic year",
                "Exactly one academic year should be marked current before attendance, subjects and results go live.",
                action_label="Manage academic years",
                action_url_name="admin_academic_year_list",
            )
        )
    elif len(current_years) > 1:
        blockers.append(
            _finding(
                "multiple_current_years",
                "More than one academic year is marked current",
                "Keep exactly one current academic year so new records do not attach to the wrong year.",
                action_label="Review academic years",
                action_url_name="admin_academic_year_list",
            )
        )

    if not current_terms:
        blockers.append(
            _finding(
                "current_term_missing",
                "Choose the current term/semester",
                "Exactly one academic period should be marked current.",
                action_label="Manage terms / semesters",
                action_url_name="admin_academic_term_list",
            )
        )
    elif len(current_terms) > 1:
        blockers.append(
            _finding(
                "multiple_current_terms",
                "More than one term/semester is marked current",
                "Keep exactly one current academic period so offerings, attendance and results use the same period.",
                action_label="Review terms / semesters",
                action_url_name="admin_academic_term_list",
            )
        )

    current_year = current_years[0] if len(current_years) == 1 else None
    current_term = current_terms[0] if len(current_terms) == 1 else None
    today = timezone.localdate()

    if current_year:
        if current_year.start_date and current_year.end_date and current_year.start_date > current_year.end_date:
            blockers.append(
                _finding(
                    "year_dates_reversed",
                    "Academic year dates are reversed",
                    "The academic year start date is after its end date.",
                    action_label="Fix academic year",
                    action_url_name="admin_academic_year_list",
                )
            )
        elif not current_year.start_date or not current_year.end_date:
            warnings.append(
                _finding(
                    "year_dates_incomplete",
                    "Add academic year dates",
                    "Dates make reports, promotions and period checks easier to verify, even though EduManage can store the year without them.",
                    action_label="Review academic year",
                    action_url_name="admin_academic_year_list",
                )
            )
        elif not (current_year.start_date <= today <= current_year.end_date):
            warnings.append(
                _finding(
                    "current_year_outside_dates",
                    "The current-year flag does not match today's date",
                    f"{current_year.name} is marked current, but today is outside {current_year.start_date} to {current_year.end_date}. Confirm that this is intentional.",
                    action_label="Review academic year",
                    action_url_name="admin_academic_year_list",
                )
            )

    if current_term:
        if current_year and current_term.year_id != current_year.pk:
            blockers.append(
                _finding(
                    "current_term_wrong_year",
                    "The current term belongs to a different academic year",
                    f"{current_term} is marked current but does not belong to the current academic year {current_year.name}.",
                    action_label="Review terms / semesters",
                    action_url_name="admin_academic_term_list",
                )
            )
        if current_term.start_date and current_term.end_date and current_term.start_date > current_term.end_date:
            blockers.append(
                _finding(
                    "term_dates_reversed",
                    "Term/semester dates are reversed",
                    "The current period start date is after its end date.",
                    action_label="Fix term / semester",
                    action_url_name="admin_academic_term_list",
                )
            )
        elif not current_term.start_date or not current_term.end_date:
            warnings.append(
                _finding(
                    "term_dates_incomplete",
                    "Add term/semester dates",
                    "Complete period dates help attendance and reporting checks identify the correct period.",
                    action_label="Review terms / semesters",
                    action_url_name="admin_academic_term_list",
                )
            )
        else:
            if current_year and current_year.start_date and current_term.start_date < current_year.start_date:
                blockers.append(
                    _finding(
                        "term_before_year",
                        "The current period starts before the academic year",
                        "Move the period dates inside the selected academic year.",
                        action_label="Fix term / semester",
                        action_url_name="admin_academic_term_list",
                    )
                )
            if current_year and current_year.end_date and current_term.end_date > current_year.end_date:
                blockers.append(
                    _finding(
                        "term_after_year",
                        "The current period ends after the academic year",
                        "Move the period dates inside the selected academic year.",
                        action_label="Fix term / semester",
                        action_url_name="admin_academic_term_list",
                    )
                )
            if not (current_term.start_date <= today <= current_term.end_date):
                warnings.append(
                    _finding(
                        "current_term_outside_dates",
                        "The current-period flag does not match today's date",
                        f"{current_term} is marked current, but today is outside {current_term.start_date} to {current_term.end_date}. Confirm that this is intentional.",
                        action_label="Review terms / semesters",
                        action_url_name="admin_academic_term_list",
                    )
                )

        if current_year:
            duplicate_orders = list(
                AcademicTerm.objects.filter(year=current_year)
                .values("order")
                .annotate(total=Count("id"))
                .filter(total__gt=1)
            )
            if duplicate_orders:
                warnings.append(
                    _finding(
                        "duplicate_period_order",
                        "Two periods use the same sequence number",
                        "Give terms/semesters distinct order numbers so EduManage can display and process them in a predictable sequence.",
                        action_label="Review terms / semesters",
                        action_url_name="admin_academic_term_list",
                    )
                )

        configured_period_types = set(
            CampusEducationStage.objects.filter(profile=profile, is_active=True, campus__is_active=True).values_list(
                "academic_period_type", flat=True
            )
        )
        if configured_period_types and current_term.type not in configured_period_types:
            warnings.append(
                _finding(
                    "period_type_mismatch",
                    "Calendar wording differs from the education structure",
                    f"The current period is a {current_term.get_type_display()}, while enabled education stages use: {', '.join(sorted(configured_period_types))}. Review this if the school expects one consistent period type.",
                    action_label="Review education structure",
                    action_url_name="admin_education_framework_dashboard",
                )
            )

    return _result(
        blockers,
        warnings,
        current_year_count=len(current_years),
        current_term_count=len(current_terms),
        current_year_id=current_year.pk if current_year else None,
        current_term_id=current_term.pk if current_term else None,
        current_year_name=current_year.name if current_year else "",
        current_term_name=str(current_term) if current_term else "",
    )


def _classes_audit(profile, active_campuses: list[Campus]) -> dict[str, Any]:
    blockers = []
    warnings = []
    active_groups = list(
        ClassGroup.objects.filter(is_active=True).select_related("campus", "level").order_by("name")
    )
    active_levels = list(Level.objects.filter(is_active=True).order_by("order", "name"))
    active_level_ids = {level.pk for level in active_levels}
    active_campus_ids = {campus.pk for campus in active_campuses}
    school_type = profile.institution_type in SCHOOL_TYPES

    if not active_groups:
        blockers.append(
            _finding(
                "classes_missing",
                "Create the classes/cohorts the institution actually teaches",
                "At least one active class group is required before subjects, attendance and learner placement can be checked.",
                action_label="Manage classes",
                action_url_name="admin_classgroup_list",
            )
        )

    if school_type:
        without_level = [row.name for row in active_groups if row.level_id is None]
        if without_level:
            blockers.append(
                _finding(
                    "class_level_missing",
                    "Some classes have no academic level",
                    "Assign a level to: " + ", ".join(without_level[:12]) + ("…" if len(without_level) > 12 else "") + ".",
                    action_label="Review classes",
                    action_url_name="admin_classgroup_list",
                )
            )

    inactive_level_groups = [row.name for row in active_groups if row.level_id and row.level_id not in active_level_ids]
    if inactive_level_groups:
        blockers.append(
            _finding(
                "class_uses_inactive_level",
                "A class uses an inactive level",
                "Review: " + ", ".join(inactive_level_groups[:12]) + ".",
                action_label="Review classes",
                action_url_name="admin_classgroup_list",
            )
        )

    inactive_campus_groups = [row.name for row in active_groups if row.campus_id and row.campus_id not in active_campus_ids]
    if inactive_campus_groups:
        blockers.append(
            _finding(
                "class_uses_inactive_campus",
                "A class belongs to an inactive campus",
                "Review: " + ", ".join(inactive_campus_groups[:12]) + ".",
                action_label="Review classes",
                action_url_name="admin_classgroup_list",
            )
        )

    unscoped_groups = [row.name for row in active_groups if row.campus_id is None]
    if unscoped_groups and len(active_campuses) > 1:
        blockers.append(
            _finding(
                "class_campus_ambiguous",
                "Some classes have no campus in a multi-campus school",
                "Choose the campus for: " + ", ".join(unscoped_groups[:12]) + ("…" if len(unscoped_groups) > 12 else "") + ".",
                action_label="Review classes",
                action_url_name="admin_classgroup_list",
            )
        )
    elif unscoped_groups and len(active_campuses) == 1:
        warnings.append(
            _finding(
                "legacy_unscoped_classes",
                "Some classes use the older campus-less format",
                "The school has one campus so these classes can still be understood, but assigning the campus explicitly makes future multi-campus setup safer.",
                action_label="Review classes",
                action_url_name="admin_classgroup_list",
            )
        )

    mapping_by_level_id = {
        row.legacy_level_id: row
        for row in LevelStageMapping.objects.filter(profile=profile).select_related("stage")
    }
    enabled_pairs = set(
        CampusEducationStage.objects.filter(
            profile=profile,
            is_active=True,
            campus__is_active=True,
            stage__is_active=True,
        ).values_list("campus_id", "stage_id")
    )
    wrong_scope_names = []
    for group in active_groups:
        if not group.level_id or not group.campus_id:
            continue
        mapping = mapping_by_level_id.get(group.level_id)
        if mapping and (group.campus_id, mapping.stage_id) not in enabled_pairs:
            wrong_scope_names.append(group.name)
    if wrong_scope_names:
        blockers.append(
            _finding(
                "class_stage_not_enabled_at_campus",
                "A class level does not belong to an education stage enabled at its campus",
                "Review: " + ", ".join(wrong_scope_names[:12]) + ".",
                action_label="Review education structure",
                action_url_name="admin_education_framework_dashboard",
            )
        )

    enabled_stage_ids = {stage_id for _campus_id, stage_id in enabled_pairs}
    in_scope_level_ids = {
        level_id
        for level_id, mapping in mapping_by_level_id.items()
        if level_id in active_level_ids and mapping.stage_id in enabled_stage_ids
    }
    represented_level_ids = {row.level_id for row in active_groups if row.level_id}
    missing_level_names = [level.name for level in active_levels if level.pk in in_scope_level_ids and level.pk not in represented_level_ids]
    if school_type and missing_level_names:
        blockers.append(
            _finding(
                "level_without_class",
                "Some active levels do not have a class group",
                "Create or review classes for: " + ", ".join(missing_level_names[:12]) + ("…" if len(missing_level_names) > 12 else "") + ".",
                action_label="Manage classes",
                action_url_name="admin_classgroup_list",
            )
        )

    duplicates = list(
        ClassGroup.objects.filter(is_active=True)
        .values("campus_id", "name")
        .annotate(total=Count("id"))
        .filter(total__gt=1)[:10]
    )
    if duplicates:
        warnings.append(
            _finding(
                "duplicate_class_names",
                "Duplicate active class names need review",
                "Two active class-group records use the same name in the same campus scope. This can confuse imports and selection lists.",
                action_label="Review classes",
                action_url_name="admin_classgroup_list",
            )
        )

    invalid_stream_count = Stream.objects.filter(is_active=True, class_group__is_active=False).count()
    if invalid_stream_count:
        blockers.append(
            _finding(
                "stream_on_inactive_class",
                "An active stream belongs to an inactive class",
                f"{invalid_stream_count} active stream(s) are attached to inactive class groups.",
                action_label="Review streams",
                action_url_name="admin_stream_list",
            )
        )
    inactive_stream_teacher_count = Stream.objects.filter(
        is_active=True,
        class_teacher__isnull=False,
        class_teacher__is_active=False,
    ).count()
    if inactive_stream_teacher_count:
        warnings.append(
            _finding(
                "inactive_stream_teacher",
                "A stream has an inactive class teacher",
                f"{inactive_stream_teacher_count} stream(s) still reference an inactive teacher.",
                action_label="Review streams",
                action_url_name="admin_stream_list",
            )
        )

    return _result(
        blockers,
        warnings,
        active_level_count=len(active_levels),
        active_class_count=len(active_groups),
        active_stream_count=Stream.objects.filter(is_active=True).count(),
        in_scope_level_count=len(in_scope_level_ids),
    )


def _subjects_audit(profile, active_campuses: list[Campus], current_term_id: int | None) -> dict[str, Any]:
    blockers = []
    warnings = []
    course_count = Course.objects.filter(is_active=True).count()
    school_type = profile.institution_type in SCHOOL_TYPES

    if not course_count:
        blockers.append(
            _finding(
                "subjects_missing",
                "Add the subjects/course units the institution teaches",
                "Create active subjects before offering them to classes.",
                action_label="Manage subjects / courses",
                action_url_name="admin_course_list",
            )
        )

    if not current_term_id:
        blockers.append(
            _finding(
                "subjects_need_current_period",
                "Finish the academic calendar first",
                "Subject offerings are period-specific, so EduManage cannot verify live offerings until exactly one current term/semester is valid.",
                action_label="Review academic calendar",
                action_url_name="admin_academic_term_list",
            )
        )
        return _result(blockers, warnings, active_course_count=course_count, current_offering_count=0)

    offerings = CourseOffering.objects.filter(is_active=True, term_id=current_term_id).select_related(
        "course", "class_group", "class_group__campus", "teacher", "teacher__campus", "campus"
    )
    current_offering_count = offerings.count()
    if not current_offering_count:
        blockers.append(
            _finding(
                "current_offerings_missing",
                "No subject offerings exist for the current period",
                "Old offerings do not make the current term ready. Add the subjects each class is taking now.",
                action_label="Manage subject offerings",
                action_url_name="admin_offering_list",
            )
        )

    if school_type:
        no_class_count = offerings.filter(class_group__isnull=True).count()
        if no_class_count:
            blockers.append(
                _finding(
                    "offering_class_missing",
                    "Some current subject offerings are not assigned to a class",
                    f"{no_class_count} current offering(s) need a class group.",
                    action_label="Review subject offerings",
                    action_url_name="admin_offering_list",
                )
            )

    inactive_course_count = offerings.filter(course__is_active=False).count()
    inactive_class_count = offerings.filter(class_group__isnull=False, class_group__is_active=False).count()
    if inactive_course_count or inactive_class_count:
        blockers.append(
            _finding(
                "offering_uses_inactive_record",
                "A current offering uses an inactive subject or class",
                f"Found {inactive_course_count} offering(s) with inactive subjects and {inactive_class_count} with inactive classes.",
                action_label="Review subject offerings",
                action_url_name="admin_offering_list",
            )
        )

    campus_class_mismatch = offerings.filter(
        campus__isnull=False,
        class_group__campus__isnull=False,
    ).exclude(campus_id=F("class_group__campus_id")).count()
    campus_teacher_mismatch = offerings.filter(
        campus__isnull=False,
        teacher__campus__isnull=False,
    ).exclude(campus_id=F("teacher__campus_id")).count()
    if campus_class_mismatch or campus_teacher_mismatch:
        blockers.append(
            _finding(
                "offering_campus_mismatch",
                "A subject offering mixes records from different campuses",
                f"Found {campus_class_mismatch} class-campus mismatch(es) and {campus_teacher_mismatch} teacher-campus mismatch(es).",
                action_label="Review subject offerings",
                action_url_name="admin_offering_list",
            )
        )

    if len(active_campuses) > 1:
        unscoped_offerings = offerings.filter(campus__isnull=True).count()
        if unscoped_offerings:
            blockers.append(
                _finding(
                    "offering_campus_missing",
                    "Some current offerings have no campus",
                    f"{unscoped_offerings} offering(s) are ambiguous in this multi-campus institution.",
                    action_label="Review subject offerings",
                    action_url_name="admin_offering_list",
                )
            )

    duplicates = list(
        offerings.values("course_id", "class_group_id", "campus_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)[:10]
    )
    if duplicates:
        blockers.append(
            _finding(
                "duplicate_current_offerings",
                "Duplicate subject offerings exist for the current period",
                "The same subject/class scope appears more than once. Keep one active offering per intended subject/class relationship.",
                action_label="Review subject offerings",
                action_url_name="admin_offering_list",
            )
        )

    active_classes = ClassGroup.objects.filter(is_active=True)
    if school_type and active_classes.exists():
        classes_with_offerings = set(offerings.exclude(class_group__isnull=True).values_list("class_group_id", flat=True))
        missing_class_names = list(
            active_classes.exclude(pk__in=classes_with_offerings).values_list("name", flat=True)[:12]
        )
        if missing_class_names:
            blockers.append(
                _finding(
                    "class_without_current_subjects",
                    "Some active classes have no subjects in the current period",
                    "Review subject offerings for: " + ", ".join(missing_class_names) + ".",
                    action_label="Manage subject offerings",
                    action_url_name="admin_offering_list",
                )
            )

    offered_course_ids = set(offerings.values_list("course_id", flat=True))
    unoffered_course_count = Course.objects.filter(is_active=True).exclude(pk__in=offered_course_ids).count()
    if unoffered_course_count:
        warnings.append(
            _finding(
                "active_subject_not_offered",
                "Some active subjects are not being taught this period",
                f"{unoffered_course_count} active subject/course record(s) have no current offering. This may be intentional; deactivate old subjects if they should no longer appear.",
                action_label="Review subjects / courses",
                action_url_name="admin_course_list",
            )
        )

    return _result(
        blockers,
        warnings,
        active_course_count=course_count,
        current_offering_count=current_offering_count,
    )


def _assessment_audit() -> dict[str, Any]:
    blockers = []
    warnings = []
    profiles = list(GradingProfile.objects.filter(is_active=True).select_related("grading_scale"))
    if not profiles:
        blockers.append(
            _finding(
                "grading_profile_missing",
                "Create an active grading profile",
                "EduManage needs a grading profile to convert results into grades, pass rules and report-card outcomes.",
                action_label="Configure grading & reports",
                action_url_name="admin_grading_framework_dashboard",
            )
        )
        return _result(blockers, warnings, active_grading_profile_count=0, report_rule_count=0)

    inactive_scale_profiles = [row.name for row in profiles if not row.grading_scale.is_active]
    if inactive_scale_profiles:
        blockers.append(
            _finding(
                "inactive_grading_scale",
                "A grading profile uses an inactive grading scale",
                "Review: " + ", ".join(inactive_scale_profiles[:10]) + ".",
                action_label="Review grading",
                action_url_name="admin_grading_framework_dashboard",
            )
        )

    rule_profile_ids = set(
        ReportRule.objects.filter(grading_profile__is_active=True).values_list("grading_profile_id", flat=True)
    )
    missing_rule_names = [row.name for row in profiles if row.pk not in rule_profile_ids]
    if missing_rule_names:
        blockers.append(
            _finding(
                "report_rule_missing",
                "Some grading profiles have no report-card rule",
                "Add report rules for: " + ", ".join(missing_rule_names[:10]) + ".",
                action_label="Configure grading & reports",
                action_url_name="admin_grading_framework_dashboard",
            )
        )

    scale_ids = {row.grading_scale_id for row in profiles}
    ranges_by_scale: dict[int, list[GradeRange]] = defaultdict(list)
    for grade_range in GradeRange.objects.filter(scale_id__in=scale_ids).order_by("scale_id", "min_score", "max_score"):
        ranges_by_scale[grade_range.scale_id].append(grade_range)

    no_range_scales = sorted({row.grading_scale.name for row in profiles if not ranges_by_scale.get(row.grading_scale_id)})
    if no_range_scales:
        blockers.append(
            _finding(
                "grading_scale_empty",
                "A grading scale has no grade ranges",
                "Add score ranges to: " + ", ".join(no_range_scales[:10]) + ".",
                action_label="Manage grading scales",
                action_url_name="admin_grading_scale_list",
            )
        )

    overlap_scales = set()
    gap_scales = set()
    invalid_range_scales = set()
    for profile in profiles:
        rows = ranges_by_scale.get(profile.grading_scale_id, [])
        if not rows:
            continue
        previous = None
        for row in rows:
            if row.min_score > row.max_score:
                invalid_range_scales.add(profile.grading_scale.name)
            if previous is not None:
                if row.min_score <= previous.max_score:
                    overlap_scales.add(profile.grading_scale.name)
                elif row.min_score > previous.max_score + Decimal("0.01"):
                    gap_scales.add(profile.grading_scale.name)
            previous = row
        if rows[0].min_score > Decimal("0") or rows[-1].max_score < Decimal("100"):
            gap_scales.add(profile.grading_scale.name)

    if invalid_range_scales or overlap_scales:
        names = sorted(invalid_range_scales | overlap_scales)
        blockers.append(
            _finding(
                "grading_ranges_invalid",
                "A grading scale has invalid or overlapping score ranges",
                "Review: " + ", ".join(names[:10]) + ". Overlapping ranges can produce ambiguous grades.",
                action_label="Manage grading scales",
                action_url_name="admin_grading_scale_list",
            )
        )
    if gap_scales:
        warnings.append(
            _finding(
                "grading_ranges_have_gaps",
                "A grading scale does not clearly cover every percentage",
                "Review: " + ", ".join(sorted(gap_scales)[:10]) + ". Confirm that gaps are intentional so every possible score can receive a grade.",
                action_label="Manage grading scales",
                action_url_name="admin_grading_scale_list",
            )
        )

    inactive_scope_count = GradingProfile.objects.filter(is_active=True).filter(
        Q(campus__is_active=False)
        | Q(stage__is_active=False)
        | Q(level__is_active=False)
        | Q(course__is_active=False)
    ).count()
    if inactive_scope_count:
        warnings.append(
            _finding(
                "grading_profile_inactive_scope",
                "A grading profile is scoped to an inactive record",
                f"{inactive_scope_count} active grading profile(s) reference an inactive campus, stage, level or subject and may never apply.",
                action_label="Review grading & reports",
                action_url_name="admin_grading_framework_dashboard",
            )
        )

    return _result(
        blockers,
        warnings,
        active_grading_profile_count=len(profiles),
        report_rule_count=len(rule_profile_ids),
    )


def _teachers_audit(active_campuses: list[Campus], current_term_id: int | None) -> dict[str, Any]:
    blockers = []
    warnings = []
    teacher_count = TeacherProfile.objects.filter(is_active=True).count()
    if not teacher_count:
        blockers.append(
            _finding(
                "teachers_missing",
                "Add active teachers",
                "At least one teacher is needed before teaching assignments can be verified.",
                action_label="Manage teachers",
                action_url_name="admin_teachers_list",
            )
        )

    if not current_term_id:
        blockers.append(
            _finding(
                "teachers_need_current_period",
                "Finish the academic calendar first",
                "Teaching assignments are verified against the current period.",
                action_label="Review academic calendar",
                action_url_name="admin_academic_term_list",
            )
        )
        return _result(blockers, warnings, active_teacher_count=teacher_count, current_offering_count=0, assigned_offering_count=0)

    offerings = CourseOffering.objects.filter(is_active=True, term_id=current_term_id)
    offering_count = offerings.count()
    if not offering_count:
        blockers.append(
            _finding(
                "teachers_need_offerings",
                "Create current subject offerings first",
                "Teachers are assigned to subject offerings, so there is nothing to verify yet.",
                action_label="Manage subject offerings",
                action_url_name="admin_offering_list",
            )
        )

    unassigned_count = offerings.filter(Q(teacher__isnull=True) | Q(teacher__is_active=False)).count()
    if unassigned_count:
        blockers.append(
            _finding(
                "offering_teacher_missing",
                "Some current subject offerings have no active teacher",
                f"Assign an active teacher to {unassigned_count} current offering(s).",
                action_label="Assign teachers",
                action_url_name="admin_offering_list",
            )
        )

    mismatch_count = offerings.filter(
        campus__isnull=False,
        teacher__campus__isnull=False,
    ).exclude(campus_id=F("teacher__campus_id")).count()
    if mismatch_count:
        blockers.append(
            _finding(
                "teacher_campus_mismatch",
                "A teacher is assigned across the wrong campus scope",
                f"{mismatch_count} current offering(s) have a teacher whose campus differs from the offering campus.",
                action_label="Review teaching assignments",
                action_url_name="admin_offering_list",
            )
        )

    if len(active_campuses) > 1:
        unscoped_teacher_count = TeacherProfile.objects.filter(is_active=True, campus__isnull=True).count()
        if unscoped_teacher_count:
            warnings.append(
                _finding(
                    "teacher_campus_missing",
                    "Some teachers have no campus",
                    f"{unscoped_teacher_count} active teacher(s) are campus-less in this multi-campus institution.",
                    action_label="Review teachers",
                    action_url_name="admin_teachers_list",
                )
            )

    duplicate_staff_ids = list(
        TeacherProfile.objects.filter(is_active=True)
        .exclude(staff_id="")
        .values("staff_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)[:10]
    )
    if duplicate_staff_ids:
        warnings.append(
            _finding(
                "duplicate_teacher_staff_ids",
                "Duplicate teacher staff IDs need review",
                "The same non-blank staff ID is used by more than one active teacher, which can confuse imports and identity matching.",
                action_label="Review teachers",
                action_url_name="admin_teachers_list",
            )
        )

    no_user_count = TeacherProfile.objects.filter(is_active=True, user__isnull=True).count()
    if no_user_count:
        warnings.append(
            _finding(
                "teacher_login_missing",
                "Some teachers do not have portal logins",
                f"{no_user_count} active teacher(s) can exist in school records but cannot sign in until a user account is linked. This does not block setup if they do not need portal access yet.",
                action_label="Review teachers",
                action_url_name="admin_teachers_list",
            )
        )

    assigned_count = offerings.filter(teacher__is_active=True).count()
    return _result(
        blockers,
        warnings,
        active_teacher_count=teacher_count,
        current_offering_count=offering_count,
        assigned_offering_count=assigned_count,
    )


def _learners_audit(active_campuses: list[Campus], current_term_id: int | None) -> dict[str, Any]:
    blockers = []
    warnings = []
    students = StudentProfile.objects.filter(is_active=True)
    student_count = students.count()
    if not student_count:
        blockers.append(
            _finding(
                "learners_missing",
                "Add or import learners",
                "At least one active learner is required before learner placement and go-live can be verified.",
                action_label="Manage students",
                action_url_name="admin_students_list",
            )
        )
        return _result(blockers, warnings, active_student_count=0, placed_student_count=0)

    active_campus_ids = {campus.pk for campus in active_campuses}
    inactive_campus_count = students.exclude(campus__isnull=True).exclude(campus_id__in=active_campus_ids).count()
    if inactive_campus_count:
        blockers.append(
            _finding(
                "student_inactive_campus",
                "Some learners belong to an inactive campus",
                f"{inactive_campus_count} active learner(s) need a valid active campus.",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )

    campus_missing_count = students.filter(campus__isnull=True).count()
    if campus_missing_count and len(active_campuses) > 1:
        blockers.append(
            _finding(
                "student_campus_missing",
                "Some learners have no campus",
                f"Choose a campus for {campus_missing_count} learner(s) in this multi-campus institution.",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )
    elif campus_missing_count and len(active_campuses) == 1:
        warnings.append(
            _finding(
                "student_campus_implicit",
                "Some learners rely on the single-campus assumption",
                f"{campus_missing_count} learner(s) have no campus recorded. They are understandable today because only one campus is active, but assigning it explicitly is safer.",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )

    invalid_stream_count = students.filter(stream__isnull=False).filter(
        Q(stream__is_active=False) | Q(stream__class_group__is_active=False)
    ).count()
    if invalid_stream_count:
        blockers.append(
            _finding(
                "student_invalid_stream",
                "Some learners are placed in an inactive stream/class",
                f"{invalid_stream_count} active learner(s) need a valid active placement.",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )

    stream_campus_mismatch = students.filter(
        campus__isnull=False,
        stream__class_group__campus__isnull=False,
    ).exclude(campus_id=F("stream__class_group__campus_id")).count()
    if stream_campus_mismatch:
        blockers.append(
            _finding(
                "student_stream_campus_mismatch",
                "A learner's campus and stream belong to different campuses",
                f"Correct {stream_campus_mismatch} learner placement(s).",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )

    placed_ids = set(
        students.filter(stream__is_active=True, stream__class_group__is_active=True).values_list("id", flat=True)
    )
    if current_term_id:
        placed_ids.update(
            Enrollment.objects.filter(
                status=Enrollment.ACTIVE,
                offering__is_active=True,
                offering__term_id=current_term_id,
                student__is_active=True,
            ).values_list("student_id", flat=True)
        )
        enrollment_campus_mismatch = Enrollment.objects.filter(
            status=Enrollment.ACTIVE,
            offering__term_id=current_term_id,
            campus__isnull=False,
            student__campus__isnull=False,
        ).exclude(campus_id=F("student__campus_id")).count()
        if enrollment_campus_mismatch:
            blockers.append(
                _finding(
                    "enrollment_campus_mismatch",
                    "A current enrollment uses a different campus from the learner",
                    f"Correct {enrollment_campus_mismatch} current enrollment(s).",
                    action_label="Review students",
                    action_url_name="admin_students_list",
                )
            )

    unplaced_count = students.exclude(pk__in=placed_ids).count()
    if unplaced_count:
        blockers.append(
            _finding(
                "student_not_placed",
                "Some learners are not connected to a class/stream or current offering",
                f"Place {unplaced_count} active learner(s) in the academic structure before go-live.",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )

    duplicate_ids = list(
        students.exclude(student_id="")
        .values("student_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)[:10]
    )
    if duplicate_ids:
        blockers.append(
            _finding(
                "duplicate_student_ids",
                "Duplicate student IDs need correction",
                "The same non-blank student ID belongs to more than one active learner. Unique IDs are important for reports, imports and payments.",
                action_label="Review students",
                action_url_name="admin_students_list",
            )
        )

    no_user_count = students.filter(user__isnull=True).count()
    if no_user_count:
        warnings.append(
            _finding(
                "student_login_missing",
                "Some learners do not have portal logins",
                f"{no_user_count} active learner(s) can remain in school records without a login. Create user accounts only for learners who need portal access.",
                action_label="Review user access",
                action_url_name="admin_users_list",
            )
        )

    return _result(
        blockers,
        warnings,
        active_student_count=student_count,
        placed_student_count=len(placed_ids),
        unplaced_student_count=unplaced_count,
    )


def _attendance_audit(active_campuses: list[Campus]) -> dict[str, Any]:
    blockers = []
    warnings = []
    policies = list(AttendancePolicy.objects.filter(is_active=True).select_related("campus"))
    active_campus_ids = {campus.pk for campus in active_campuses}
    invalid_campus_count = sum(1 for row in policies if row.campus_id and row.campus_id not in active_campus_ids)
    if invalid_campus_count:
        blockers.append(
            _finding(
                "attendance_policy_inactive_campus",
                "An attendance policy belongs to an inactive campus",
                f"Review {invalid_campus_count} active attendance policy/policies.",
                action_label="Review attendance policies",
                action_url_name="admin_attendance_policy_list",
            )
        )

    bad_weekdays = 0
    for policy in policies:
        weekdays = policy.weekdays or []
        if any(not isinstance(day, int) or day < 0 or day > 6 for day in weekdays):
            bad_weekdays += 1
    if bad_weekdays:
        blockers.append(
            _finding(
                "attendance_weekdays_invalid",
                "An attendance policy has invalid weekdays",
                f"{bad_weekdays} policy/policies contain weekday values outside Monday-Sunday.",
                action_label="Review attendance policies",
                action_url_name="admin_attendance_policy_list",
            )
        )

    duplicate_defaults = list(
        AttendancePolicy.objects.filter(is_active=True, is_default=True)
        .values("person_type", "campus_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)[:10]
    )
    if duplicate_defaults:
        blockers.append(
            _finding(
                "attendance_multiple_defaults",
                "More than one default attendance policy uses the same scope",
                "Keep one default policy per person type/campus so attendance rules are predictable.",
                action_label="Review attendance policies",
                action_url_name="admin_attendance_policy_list",
            )
        )

    staff_time_missing = sum(
        1
        for row in policies
        if row.person_type == AttendancePolicy.STAFF and (row.expected_in is None or row.expected_out is None)
    )
    if staff_time_missing:
        warnings.append(
            _finding(
                "staff_attendance_times_incomplete",
                "Some staff policies do not define both reporting and sign-out times",
                f"{staff_time_missing} staff policy/policies can still track presence, but lateness or early-departure reporting may be incomplete.",
                action_label="Review attendance policies",
                action_url_name="admin_attendance_policy_list",
            )
        )

    return _result(blockers, warnings, active_policy_count=len(policies))


def _finance_audit(org) -> dict[str, Any]:
    blockers = []
    warnings = []
    items = FeeItem.objects.filter(is_active=True)
    item_count = items.count()
    if item_count:
        negative_count = items.filter(amount__lt=0).count()
        zero_count = items.filter(amount=0).count()
        if negative_count:
            blockers.append(
                _finding(
                    "negative_fee_items",
                    "A fee item has a negative amount",
                    f"Correct {negative_count} active fee item(s) before using them on invoices.",
                    action_label="Review fee items",
                    action_url_name="admin_fee_items_list",
                )
            )
        if zero_count:
            warnings.append(
                _finding(
                    "zero_fee_items",
                    "Some active fee items have a zero amount",
                    f"{zero_count} fee item(s) are zero. Keep them only if zero is intentional.",
                    action_label="Review fee items",
                    action_url_name="admin_fee_items_list",
                )
            )
        duplicate_names = list(
            items.values("name").annotate(total=Count("id")).filter(total__gt=1)[:10]
        )
        if duplicate_names:
            warnings.append(
                _finding(
                    "duplicate_fee_names",
                    "Duplicate active fee names need review",
                    "Different fee codes may intentionally share a name, but duplicate labels can confuse invoice entry.",
                    action_label="Review fee items",
                    action_url_name="admin_fee_items_list",
                )
            )
    currency = (getattr(org, "default_currency", "") or "").strip().upper()
    if item_count and len(currency) != 3:
        blockers.append(
            _finding(
                "currency_invalid",
                "Set a valid 3-letter currency code",
                "Finance is enabled but the institution currency is not a valid three-letter code such as UGX or USD.",
                action_label="Edit institution profile",
                action_url_name="admin_orgsettings_org",
            )
        )

    return _result(blockers, warnings, active_fee_item_count=item_count)


def school_setup_audit(org, profile) -> dict[str, Any]:
    """Return a cross-model validity snapshot for every setup stage."""
    active_campuses = list(
        Campus.objects.filter(organization=org, is_active=True).order_by("name")
    )
    institution = _institution_audit(org, active_campuses)
    education = _education_structure_audit(org, profile, active_campuses)
    calendar = _calendar_audit(profile)
    current_term_id = calendar["metrics"].get("current_term_id")

    steps = {
        "institution": institution,
        "education_structure": education,
        "calendar": calendar,
        "classes": _classes_audit(profile, active_campuses),
        "subjects": _subjects_audit(profile, active_campuses, current_term_id),
        "assessment": _assessment_audit(),
        "teaching": _teachers_audit(active_campuses, current_term_id),
        "learners": _learners_audit(active_campuses, current_term_id),
        "attendance": _attendance_audit(active_campuses),
        "finance": _finance_audit(org),
    }

    blocker_count = sum(len(row["blockers"]) for row in steps.values())
    warning_count = sum(len(row["warnings"]) for row in steps.values())
    return {
        "steps": steps,
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "core_blocker_count": sum(
            len(steps[key]["blockers"])
            for key in (
                "institution",
                "education_structure",
                "calendar",
                "classes",
                "subjects",
                "assessment",
                "teaching",
                "learners",
            )
        ),
    }
