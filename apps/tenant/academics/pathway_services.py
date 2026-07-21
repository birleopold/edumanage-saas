from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import (
    AcademicTerm,
    ClassGroup,
    ClassGroupPathwayAssignment,
    Course,
    CourseOffering,
    Level,
    Program,
    ProgrammePathway,
    ProgrammePathwayLevel,
    SubjectCombination,
    SubjectCombinationCourse,
    normalize_academic_code,
)


@dataclass(frozen=True)
class PathwayResolution:
    assignment: ClassGroupPathwayAssignment | None
    pathway: ProgrammePathway | None
    combination: SubjectCombination | None


@dataclass(frozen=True)
class OfferingPlanRow:
    membership: SubjectCombinationCourse
    offering: CourseOffering | None

    @property
    def exists(self) -> bool:
        return self.offering is not None


def pathway_errors(pathway: ProgrammePathway) -> list[str]:
    errors = []
    try:
        pathway.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)

    levels = list(pathway.pathway_levels.filter(is_active=True).select_related("level")) if pathway.pk else []
    if not levels:
        errors.append("Add at least one active level to the pathway.")
    else:
        entry_count = sum(1 for item in levels if item.is_entry)
        exit_count = sum(1 for item in levels if item.is_exit)
        if entry_count != 1:
            errors.append("The pathway must have exactly one active entry level.")
        if exit_count != 1:
            errors.append("The pathway must have exactly one active exit level.")
    return list(dict.fromkeys(errors))


def pathway_is_ready(pathway: ProgrammePathway) -> bool:
    return bool(pathway.is_active and not pathway_errors(pathway))


def combination_errors(combination: SubjectCombination) -> list[str]:
    errors = []
    try:
        combination.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)

    memberships = list(
        combination.course_memberships.filter(is_active=True).select_related("course")
    ) if combination.pk else []
    active_count = len(memberships)
    if not active_count:
        errors.append("Add at least one active course to the combination.")
    if active_count and combination.minimum_subjects > active_count:
        errors.append("Minimum subjects cannot exceed the number of active courses.")
    if combination.maximum_subjects is not None and active_count:
        if combination.maximum_subjects > active_count:
            errors.append("Maximum subjects cannot exceed the number of active courses.")
    return list(dict.fromkeys(errors))


def combination_is_ready(combination: SubjectCombination) -> bool:
    return bool(combination.is_active and not combination_errors(combination))


def assignment_errors(assignment: ClassGroupPathwayAssignment) -> list[str]:
    errors = []
    try:
        assignment.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    if assignment.pathway_id and not pathway_is_ready(assignment.pathway):
        errors.append("The selected pathway is not structurally ready.")
    if assignment.subject_combination_id and not combination_is_ready(assignment.subject_combination):
        errors.append("The selected subject combination is not structurally ready.")
    return list(dict.fromkeys(errors))


def _default_combination(pathway: ProgrammePathway, class_group: ClassGroup) -> SubjectCombination | None:
    candidates = pathway.subject_combinations.filter(is_active=True).select_related("level", "pathway").prefetch_related(
        "course_memberships__course"
    )
    matched = []
    for combination in candidates:
        if combination.level_id and combination.level_id != class_group.level_id:
            continue
        if combination_is_ready(combination):
            specificity = int(bool(combination.level_id and combination.level_id == class_group.level_id))
            matched.append((combination.priority, specificity, int(combination.is_default), combination.pk, combination))
    return max(matched, default=(0, 0, 0, 0, None))[-1]


def resolve_class_group_pathway(
    class_group: ClassGroup,
    term: AcademicTerm | None = None,
) -> PathwayResolution:
    assignments = ClassGroupPathwayAssignment.objects.filter(
        class_group=class_group,
        is_active=True,
    ).filter(Q(academic_term=term) | Q(academic_term__isnull=True)).select_related(
        "pathway",
        "pathway__program",
        "pathway__campus",
        "pathway__stage",
        "subject_combination",
        "academic_term",
        "class_group",
        "class_group__program",
        "class_group__level",
        "class_group__campus",
    ).prefetch_related(
        "pathway__pathway_levels__level",
        "pathway__subject_combinations__course_memberships__course",
        "subject_combination__course_memberships__course",
    )

    ranked = []
    for assignment in assignments:
        if assignment_errors(assignment):
            continue
        exact_term = int(bool(term and assignment.academic_term_id == term.pk))
        combination = assignment.subject_combination or _default_combination(assignment.pathway, class_group)
        if combination and not combination_is_ready(combination):
            combination = None
        ranked.append(
            (
                exact_term,
                assignment.pathway.priority,
                int(assignment.pathway.is_default),
                assignment.pk,
                assignment,
                combination,
            )
        )

    if not ranked:
        return PathwayResolution(None, None, None)
    selected = max(ranked)
    return PathwayResolution(selected[-2], selected[-2].pathway, selected[-1])


def resolve_student_pathway(student, term: AcademicTerm | None = None) -> PathwayResolution:
    if not getattr(student, "stream_id", None):
        return PathwayResolution(None, None, None)
    class_group = student.stream.class_group
    return resolve_class_group_pathway(class_group, term)


def offering_plan(class_group: ClassGroup, term: AcademicTerm) -> dict:
    resolution = resolve_class_group_pathway(class_group, term)
    rows = []
    if resolution.combination:
        memberships = resolution.combination.course_memberships.filter(
            is_active=True,
            course__is_active=True,
        ).select_related("course").order_by("order", "course__name")
        for membership in memberships:
            offering = CourseOffering.objects.filter(
                class_group=class_group,
                term=term,
                course=membership.course,
            ).order_by("pk").first()
            rows.append(OfferingPlanRow(membership=membership, offering=offering))
    return {
        "class_group": class_group,
        "term": term,
        "resolution": resolution,
        "rows": rows,
        "existing_count": sum(1 for row in rows if row.exists),
        "missing_count": sum(1 for row in rows if not row.exists),
    }


@transaction.atomic
def create_missing_offerings(class_group: ClassGroup, term: AcademicTerm, *, dry_run=False) -> dict:
    plan = offering_plan(class_group, term)
    created = 0
    existing = plan["existing_count"]
    for row in plan["rows"]:
        if row.exists:
            continue
        created += 1
        if not dry_run:
            CourseOffering.objects.create(
                campus=class_group.campus,
                class_group=class_group,
                course=row.membership.course,
                term=term,
                is_active=True,
            )
    return {
        **plan,
        "created_count": created,
        "existing_count": existing,
        "dry_run": dry_run,
    }


def _programme_levels(program: Program) -> list[Level]:
    ids = set(
        ClassGroup.objects.filter(program=program, level__isnull=False, level__is_active=True).values_list(
            "level_id", flat=True
        )
    )
    ids.update(
        Course.objects.filter(program=program, level__isnull=False, level__is_active=True).values_list(
            "level_id", flat=True
        )
    )
    return list(Level.objects.filter(pk__in=ids, is_active=True).order_by("order", "name"))


def bootstrap_programme_pathways(*, dry_run=False) -> dict:
    summary = {
        "pathways_created": 0,
        "pathways_existing": 0,
        "levels_created": 0,
        "combinations_created": 0,
        "combinations_existing": 0,
        "courses_linked": 0,
        "assignments_created": 0,
    }
    for program in Program.objects.filter(is_active=True).order_by("name"):
        token = normalize_academic_code(program.code or program.name)[:36] or f"PROGRAM-{program.pk}"
        pathway_code = f"PATH-{token}"
        combination_code = f"COMB-{token}"
        pathway = ProgrammePathway.objects.filter(code=pathway_code).first()
        if pathway:
            summary["pathways_existing"] += 1
        else:
            summary["pathways_created"] += 1
            if not dry_run:
                pathway = ProgrammePathway.objects.create(
                    code=pathway_code,
                    name=f"{program.name} Pathway",
                    description="Created from the existing programme without changing programme records.",
                    program=program,
                    is_default=True,
                    is_active=True,
                )

        levels = _programme_levels(program)
        for index, level in enumerate(levels, start=1):
            exists = bool(pathway and pathway.pathway_levels.filter(level=level).exists())
            if not exists:
                summary["levels_created"] += 1
                if not dry_run and pathway:
                    ProgrammePathwayLevel.objects.create(
                        pathway=pathway,
                        level=level,
                        sequence=index,
                        is_entry=index == 1,
                        is_exit=index == len(levels),
                        is_active=True,
                    )

        combination = SubjectCombination.objects.filter(code=combination_code).first()
        if combination:
            summary["combinations_existing"] += 1
        else:
            summary["combinations_created"] += 1
            if not dry_run and pathway:
                courses = list(Course.objects.filter(program=program, is_active=True).order_by("name"))
                combination = SubjectCombination.objects.create(
                    code=combination_code,
                    name=f"{program.name} Default Subjects",
                    description="Created from courses already linked to the programme.",
                    pathway=pathway,
                    minimum_subjects=max(len(courses), 1),
                    maximum_subjects=len(courses) or None,
                    is_default=True,
                    is_active=True,
                )

        courses = list(Course.objects.filter(program=program, is_active=True).order_by("name"))
        for index, course in enumerate(courses, start=1):
            exists = bool(combination and combination.course_memberships.filter(course=course).exists())
            if not exists:
                summary["courses_linked"] += 1
                if not dry_run and combination:
                    SubjectCombinationCourse.objects.create(
                        combination=combination,
                        course=course,
                        role=SubjectCombinationCourse.CORE,
                        order=index,
                        is_active=True,
                    )
    return summary


def pathway_framework_readiness() -> dict:
    pathways = list(
        ProgrammePathway.objects.select_related("program", "campus", "stage").prefetch_related(
            "pathway_levels__level",
            "subject_combinations__course_memberships__course",
        )
    )
    combinations = list(
        SubjectCombination.objects.select_related("pathway", "level").prefetch_related(
            "course_memberships__course"
        )
    )
    assignments = list(
        ClassGroupPathwayAssignment.objects.select_related(
            "class_group",
            "class_group__program",
            "class_group__level",
            "class_group__campus",
            "pathway",
            "pathway__program",
            "subject_combination",
            "academic_term",
        ).prefetch_related(
            "pathway__pathway_levels__level",
            "pathway__subject_combinations__course_memberships__course",
            "subject_combination__course_memberships__course",
        )
    )
    invalid_pathways = [
        {"pathway": pathway, "errors": pathway_errors(pathway)}
        for pathway in pathways
        if pathway_errors(pathway)
    ]
    invalid_combinations = [
        {"combination": combination, "errors": combination_errors(combination)}
        for combination in combinations
        if combination_errors(combination)
    ]
    invalid_assignments = [
        {"assignment": assignment, "errors": assignment_errors(assignment)}
        for assignment in assignments
        if assignment_errors(assignment)
    ]
    assigned_class_ids = {
        assignment.class_group_id for assignment in assignments if assignment.is_active and not assignment_errors(assignment)
    }
    eligible_classes = ClassGroup.objects.filter(is_active=True, program__isnull=False)
    unassigned_count = eligible_classes.exclude(pk__in=assigned_class_ids).count()
    active_program_count = Program.objects.filter(is_active=True).count()
    active_pathway_count = sum(1 for pathway in pathways if pathway.is_active)
    checks = {
        "pathways_available": active_program_count == 0 or active_pathway_count > 0,
        "pathways_valid": not invalid_pathways,
        "combinations_valid": not invalid_combinations,
        "assignments_valid": not invalid_assignments,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "pathway_count": len(pathways),
        "active_pathway_count": active_pathway_count,
        "combination_count": len(combinations),
        "assignment_count": len(assignments),
        "unassigned_class_group_count": unassigned_count,
        "invalid_pathways": invalid_pathways,
        "invalid_pathway_count": len(invalid_pathways),
        "invalid_combinations": invalid_combinations,
        "invalid_combination_count": len(invalid_combinations),
        "invalid_assignments": invalid_assignments,
        "invalid_assignment_count": len(invalid_assignments),
    }
