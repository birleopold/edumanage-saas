from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db.models import F, Q, QuerySet

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile

from .models import (
    Assessment,
    AssessmentScore,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
)


@dataclass(frozen=True)
class GradeBand:
    min_percentage: Decimal
    letter: str
    remark: str


DEFAULT_GRADE_BANDS = (
    GradeBand(Decimal("80"), "A", "Excellent"),
    GradeBand(Decimal("70"), "B", "Very good"),
    GradeBand(Decimal("60"), "C", "Good"),
    GradeBand(Decimal("50"), "D", "Fair"),
    GradeBand(Decimal("0"), "F", "Needs improvement"),
)


@dataclass(frozen=True)
class ScoreResult:
    score: Decimal | None
    max_score: Decimal
    percentage: Decimal | None
    grade: str
    remark: str
    note: str
    report_comment: str
    report_comment_ai_assisted: bool
    is_missing: bool


@dataclass(frozen=True)
class ComponentSourceResult:
    source_kind: str
    source: object
    score: Decimal | None
    max_score: Decimal
    percentage: Decimal | None
    date: object | None


@dataclass(frozen=True)
class ComponentResult:
    component: AssessmentWeightingComponent
    percentage: Decimal | None
    contribution: Decimal
    occurrence_count: int
    completed_count: int
    is_complete: bool
    sources: list[ComponentSourceResult] = field(default_factory=list)


@dataclass(frozen=True)
class SchemeResult:
    scheme: AssessmentWeightingScheme
    percentage: Decimal | None
    contribution_total: Decimal
    denominator_weight: Decimal
    is_complete: bool
    missing_components: list[AssessmentWeightingComponent]
    components: list[ComponentResult]


@dataclass(frozen=True)
class CourseResult:
    offering: CourseOffering
    assessments: list[dict]
    total_weight: Decimal
    weighted_percentage: Decimal | None
    simple_percentage: Decimal | None
    grade: str
    remark: str
    completed_count: int
    assessment_count: int
    scheme: AssessmentWeightingScheme | None = None
    is_complete: bool = True
    component_results: list[ComponentResult] = field(default_factory=list)


@dataclass(frozen=True)
class ReportCard:
    student: StudentProfile
    course_results: list[CourseResult]
    overall_percentage: Decimal | None
    overall_grade: str
    overall_remark: str
    published_assessment_count: int
    completed_assessment_count: int


ASSESSMENT_TYPE_TEMPLATES = (
    ("QUIZ", "Quiz", AssessmentType.CONTINUOUS, "Short formative assessment or knowledge check.", {}),
    ("TEST", "Test", AssessmentType.CONTINUOUS, "General classroom or topic test.", {}),
    ("ASSIGNMENT", "Assignment", AssessmentType.COURSEWORK, "Individual or group assignment.", {}),
    ("PROJECT", "Project", AssessmentType.PROJECT, "Extended project, investigation or portfolio activity.", {}),
    ("PRACTICAL", "Practical", AssessmentType.PRACTICAL, "Laboratory, workshop, studio or field practical.", {}),
    ("COURSEWORK", "Coursework", AssessmentType.COURSEWORK, "Combined coursework or continuous-assessment component.", {}),
    ("ORAL", "Oral or Presentation", AssessmentType.ORAL, "Oral examination, presentation, recital or demonstration.", {}),
    ("EXAM", "Examination", AssessmentType.EXAMINATION, "Formal internal or external examination component.", {}),
    ("BOT", "Beginning of Term Test", AssessmentType.CONTINUOUS, "Uganda-oriented beginning-of-term assessment.", {"UG": "BOT"}),
    ("MOT", "Mid-Term Test", AssessmentType.CONTINUOUS, "Uganda-oriented mid-term assessment.", {"UG": "MOT"}),
    ("EOT", "End of Term Examination", AssessmentType.EXAMINATION, "Uganda-oriented end-of-term examination.", {"UG": "EOT"}),
    ("AOI", "Activity of Integration", AssessmentType.COMPETENCY, "Competency-based activity integrating knowledge, skills and values.", {"UG": "AOI"}),
)


def _to_decimal(value, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def quantize_percent(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percentage(score: Decimal | None, max_score: Decimal | None) -> Decimal | None:
    score_dec = _to_decimal(score)
    max_dec = _to_decimal(max_score)
    if score_dec is None or max_dec is None or max_dec <= 0:
        return None
    return quantize_percent((score_dec / max_dec) * Decimal("100"))


def grade_for_percentage(value: Decimal | None, bands: Iterable[GradeBand] = DEFAULT_GRADE_BANDS) -> tuple[str, str]:
    if value is None:
        return "-", "Not graded"
    for band in sorted(bands, key=lambda b: b.min_percentage, reverse=True):
        if value >= band.min_percentage:
            return band.letter, band.remark
    return "-", "Not graded"


def validate_score(score_raw, max_score: Decimal) -> tuple[Decimal | None, str | None]:
    if score_raw in (None, ""):
        return None, None
    score = _to_decimal(score_raw)
    if score is None:
        return None, "Invalid score. Enter a valid number."
    if score < 0:
        return None, "Score cannot be negative."
    max_score = _to_decimal(max_score, Decimal("0")) or Decimal("0")
    if max_score > 0 and score > max_score:
        return None, f"Score cannot exceed {max_score}."
    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), None


def score_result(assessment: Assessment, score: AssessmentScore | None) -> ScoreResult:
    value = score.score if score else None
    pct = percentage(value, assessment.max_score)
    grade, remark = grade_for_percentage(pct)
    return ScoreResult(
        score=value,
        max_score=assessment.max_score,
        percentage=pct,
        grade=grade,
        remark=remark,
        note=score.note if score else "",
        report_comment=score.report_comment if score else "",
        report_comment_ai_assisted=bool(score.report_comment_ai_assisted) if score else False,
        is_missing=value is None,
    )


def ensure_assessment_type_templates() -> dict[str, AssessmentType]:
    result = {}
    for code, name, kind, description, local_aliases in ASSESSMENT_TYPE_TEMPLATES:
        obj, _ = AssessmentType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "description": description,
                "local_aliases": local_aliases,
                "is_system": True,
                "is_active": True,
            },
        )
        result[code] = obj
    return result


def infer_assessment_type_code(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()
    compact = normalized.replace(" ", "")
    if re.search(r"\b(bot|beginning of term|start of term)\b", normalized) or compact == "bot":
        return "BOT"
    if re.search(r"\b(mot|mid term|midterm)\b", normalized) or compact == "mot":
        return "MOT"
    if re.search(r"\b(eot|end of term|end term|final exam)\b", normalized) or compact == "eot":
        return "EOT"
    if re.search(r"\b(aoi|activity of integration|integration activity)\b", normalized) or compact == "aoi":
        return "AOI"
    if "quiz" in normalized:
        return "QUIZ"
    if "assignment" in normalized or "homework" in normalized:
        return "ASSIGNMENT"
    if "project" in normalized or "portfolio" in normalized:
        return "PROJECT"
    if any(token in normalized for token in ("practical", "laboratory", "lab test", "workshop")):
        return "PRACTICAL"
    if any(token in normalized for token in ("oral", "presentation", "recital", "viva")):
        return "ORAL"
    if "coursework" in normalized or "course work" in normalized:
        return "COURSEWORK"
    if any(token in normalized for token in ("exam", "examination", "paper")):
        return "EXAM"
    return "TEST"


def scheme_validation_errors(scheme: AssessmentWeightingScheme) -> list[str]:
    errors = []
    if scheme.pk and AssessmentWeightingScheme.objects.filter(
        campus_id=scheme.campus_id,
        stage_id=scheme.stage_id,
        academic_term_id=scheme.academic_term_id,
        program_id=scheme.program_id,
        priority=scheme.priority,
        is_active=True,
    ).exclude(pk=scheme.pk).exists():
        errors.append("Another active scheme has the same scope and priority.")
    components = list(scheme.components.filter(is_active=True).select_related("assessment_type"))
    if not components:
        errors.append("The scheme has no active weighting components.")
        return errors
    component_total = sum((_to_decimal(component.weight, Decimal("0")) or Decimal("0")) for component in components)
    expected = _to_decimal(scheme.total_weight, Decimal("0")) or Decimal("0")
    if abs(component_total - expected) > Decimal("0.01"):
        errors.append(f"Active component weights total {component_total}, but the scheme total is {expected}.")
    for component in components:
        try:
            component.full_clean()
        except ValidationError as exc:
            errors.extend(f"{component.assessment_type}: {message}" for message in exc.messages)
        if not component.assessment_type.is_active:
            errors.append(f"{component.assessment_type} is inactive.")
    return errors


def scheme_is_ready(scheme: AssessmentWeightingScheme) -> bool:
    return bool(scheme.is_active and not scheme_validation_errors(scheme))


def offering_program(offering: CourseOffering):
    if offering.class_group_id and offering.class_group.program_id:
        return offering.class_group.program
    return offering.course.program if offering.course_id and offering.course.program_id else None


def offering_stage(offering: CourseOffering):
    level = None
    if offering.class_group_id and offering.class_group.level_id:
        level = offering.class_group.level
    elif offering.course_id and offering.course.level_id:
        level = offering.course.level
    if not level:
        return None
    try:
        from apps.tenant.education_frameworks.models import InstitutionEducationProfile
        from apps.tenant.education_frameworks.services import resolve_level_stage

        profile = InstitutionEducationProfile.objects.filter(is_active=True).first()
        if profile:
            return resolve_level_stage(level, profile)
    except Exception:
        return None
    return None


def _scope_matches(scheme: AssessmentWeightingScheme, offering: CourseOffering, stage, program) -> bool:
    return bool(
        (scheme.campus_id is None or scheme.campus_id == offering.campus_id)
        and (scheme.academic_term_id is None or scheme.academic_term_id == offering.term_id)
        and (scheme.program_id is None or (program and scheme.program_id == program.pk))
        and (scheme.stage_id is None or (stage and scheme.stage_id == stage.pk))
    )


def _scheme_specificity(scheme: AssessmentWeightingScheme, offering: CourseOffering, stage, program) -> tuple:
    exact = sum(
        (
            bool(scheme.campus_id and scheme.campus_id == offering.campus_id),
            bool(scheme.academic_term_id and scheme.academic_term_id == offering.term_id),
            bool(scheme.program_id and program and scheme.program_id == program.pk),
            bool(scheme.stage_id and stage and scheme.stage_id == stage.pk),
        )
    )
    return (scheme.priority, exact, int(scheme.is_default), scheme.pk or 0)


def resolve_weighting_scheme(offering: CourseOffering) -> AssessmentWeightingScheme | None:
    stage = offering_stage(offering)
    program = offering_program(offering)
    candidates = AssessmentWeightingScheme.objects.filter(is_active=True).select_related(
        "campus", "stage", "academic_term", "program"
    ).prefetch_related("components__assessment_type")
    matched = [
        scheme
        for scheme in candidates
        if _scope_matches(scheme, offering, stage, program) and scheme_is_ready(scheme)
    ]
    if not matched:
        return None
    return max(matched, key=lambda scheme: _scheme_specificity(scheme, offering, stage, program))


def matching_component(scheme: AssessmentWeightingScheme | None, assessment_type: AssessmentType | None):
    if not scheme or not assessment_type:
        return None
    return scheme.components.filter(
        assessment_type=assessment_type,
        is_active=True,
    ).select_related("assessment_type", "scheme").first()


def classify_existing_records(*, dry_run: bool = False, include_exam_papers: bool = True) -> dict[str, int]:
    if dry_run:
        types = {item.code: item for item in AssessmentType.objects.filter(is_active=True)}
        missing = {template[0] for template in ASSESSMENT_TYPE_TEMPLATES} - set(types)
        if missing:
            raise ValidationError(
                "Assessment type templates must be seeded before classification preview: "
                + ", ".join(sorted(missing))
            )
    else:
        types = ensure_assessment_type_templates()
    summary = {
        "assessments_classified": 0,
        "assessments_linked": 0,
        "exam_papers_classified": 0,
        "exam_papers_linked": 0,
        "unchanged": 0,
    }
    for assessment in Assessment.objects.select_related("offering", "assessment_type", "weighting_component"):
        changed_fields = []
        inferred = assessment.assessment_type or types[infer_assessment_type_code(assessment.name)]
        if not assessment.assessment_type_id:
            assessment.assessment_type = inferred
            changed_fields.append("assessment_type")
            summary["assessments_classified"] += 1
        if not assessment.weighting_component_id:
            component = matching_component(resolve_weighting_scheme(assessment.offering), inferred)
            if component:
                assessment.weighting_component = component
                changed_fields.append("weighting_component")
                summary["assessments_linked"] += 1
        if changed_fields and not dry_run:
            assessment.save(update_fields=changed_fields)
        if not changed_fields:
            summary["unchanged"] += 1

    if include_exam_papers:
        try:
            from apps.tenant.exams.models import ExamPaper
        except Exception:
            ExamPaper = None
        if ExamPaper is not None:
            papers = ExamPaper.objects.select_related("exam", "offering", "assessment_type", "weighting_component")
            for paper in papers:
                changed_fields = []
                inferred_name = f"{paper.exam.name} {paper.offering.course.name}"
                inferred = paper.assessment_type or types[infer_assessment_type_code(inferred_name)]
                if not paper.assessment_type_id:
                    paper.assessment_type = inferred
                    changed_fields.append("assessment_type")
                    summary["exam_papers_classified"] += 1
                if not paper.weighting_component_id:
                    component = matching_component(resolve_weighting_scheme(paper.offering), inferred)
                    if component:
                        paper.weighting_component = component
                        changed_fields.append("weighting_component")
                        summary["exam_papers_linked"] += 1
                if changed_fields and not dry_run:
                    paper.save(update_fields=changed_fields)
                if not changed_fields:
                    summary["unchanged"] += 1
    return summary


def ensure_exam_paper_assessment_link(paper, *, create: bool = False):
    """Return or explicitly create an Assessment compatibility record for an exam paper.

    The function never copies ExamScore rows. Configurable aggregation reads ExamScore
    directly, so the link is metadata-only and safe to enable gradually.
    """

    if paper.linked_assessment_id:
        return paper.linked_assessment
    if not create:
        return None
    base_name = f"{paper.exam.name} - {paper.offering.course.name}"
    name = base_name[:128]
    assessment, _ = Assessment.objects.get_or_create(
        offering=paper.offering,
        name=name,
        defaults={
            "assessment_type": paper.assessment_type,
            "weighting_component": paper.weighting_component,
            "max_score": paper.max_score,
            "weight": paper.weight,
            "date": paper.date,
            "is_published": paper.results_are_visible(),
        },
    )
    changed = []
    for field_name in ("assessment_type", "weighting_component", "max_score", "weight", "date"):
        value = getattr(paper, field_name)
        if getattr(assessment, field_name) != value:
            setattr(assessment, field_name, value)
            changed.append(field_name)
    visible = paper.results_are_visible()
    if assessment.is_published != visible:
        assessment.is_published = visible
        changed.append("is_published")
    if changed:
        assessment.save(update_fields=changed)
    paper.linked_assessment = assessment
    paper.save(update_fields=["linked_assessment"])
    return assessment


def create_missing_exam_paper_links(*, dry_run: bool = False) -> dict[str, int]:
    try:
        from apps.tenant.exams.models import ExamPaper
    except Exception:
        return {"created": 0, "existing": 0}
    summary = {"created": 0, "existing": 0}
    for paper in ExamPaper.objects.select_related(
        "exam", "offering", "offering__course", "assessment_type", "weighting_component", "linked_assessment"
    ):
        if paper.linked_assessment_id:
            summary["existing"] += 1
            continue
        summary["created"] += 1
        if not dry_run:
            ensure_exam_paper_assessment_link(paper, create=True)
    return summary


def active_offerings_for_student(student: StudentProfile) -> QuerySet:
    return CourseOffering.objects.filter(
        enrollment__student=student,
        enrollment__status=Enrollment.ACTIVE,
        is_active=True,
    ).select_related(
        "course",
        "course__level",
        "course__program",
        "term",
        "term__year",
        "class_group",
        "class_group__level",
        "class_group__program",
        "teacher",
        "campus",
    ).distinct()


def published_assessments_for_student(student: StudentProfile) -> QuerySet:
    return Assessment.objects.filter(
        offering__in=active_offerings_for_student(student),
        is_published=True,
    ).select_related(
        "assessment_type",
        "weighting_component",
        "offering",
        "offering__course",
        "offering__course__level",
        "offering__course__program",
        "offering__term",
        "offering__term__year",
        "offering__class_group",
        "offering__class_group__level",
        "offering__class_group__program",
        "offering__teacher",
        "offering__campus",
    ).order_by("offering__term__year__name", "offering__term__order", "offering__course__name", "date", "name")


def score_map_for_student(student: StudentProfile, assessments: Iterable[Assessment]) -> dict[int, AssessmentScore]:
    assessment_ids = [assessment.id for assessment in assessments]
    return {
        score.assessment_id: score
        for score in AssessmentScore.objects.filter(student=student, assessment_id__in=assessment_ids)
        .select_related("assessment", "student", "graded_by")
    }


def _assessment_sources(component, offering, student, published_only=True) -> list[ComponentSourceResult]:
    filters = Q(weighting_component=component) | Q(
        weighting_component__isnull=True,
        assessment_type=component.assessment_type,
    )
    qs = Assessment.objects.filter(offering=offering).filter(filters).distinct()
    if published_only:
        qs = qs.filter(is_published=True)
    score_by_assessment = {
        score.assessment_id: score
        for score in AssessmentScore.objects.filter(
            student=student,
            assessment__in=qs,
        )
    }
    rows = []
    for assessment in qs.order_by("date", "created_at", "pk"):
        score = score_by_assessment.get(assessment.pk)
        value = score.score if score else None
        rows.append(
            ComponentSourceResult(
                source_kind="assessment",
                source=assessment,
                score=value,
                max_score=assessment.max_score,
                percentage=percentage(value, assessment.max_score),
                date=assessment.date,
            )
        )
    return rows


def _exam_sources(component, offering, student, published_only=True) -> list[ComponentSourceResult]:
    try:
        from apps.tenant.exams.models import ExamPaper, ExamScore
    except Exception:
        return []
    filters = Q(weighting_component=component) | Q(
        weighting_component__isnull=True,
        assessment_type=component.assessment_type,
    )
    qs = ExamPaper.objects.filter(offering=offering).filter(filters).distinct()
    if published_only:
        qs = qs.filter(Q(results_published=True) | Q(show_results_immediately=True))
    score_by_paper = {
        score.paper_id: score
        for score in ExamScore.objects.filter(student=student, paper__in=qs)
    }
    rows = []
    for paper in qs.select_related("exam").order_by("date", "created_at", "pk"):
        score = score_by_paper.get(paper.pk)
        value = score.score if score else None
        rows.append(
            ComponentSourceResult(
                source_kind="exam_paper",
                source=paper,
                score=value,
                max_score=paper.max_score,
                percentage=percentage(value, paper.max_score),
                date=paper.date,
            )
        )
    return rows


def component_sources(component, offering, student, *, published_only=True) -> list[ComponentSourceResult]:
    return _assessment_sources(component, offering, student, published_only) + _exam_sources(
        component, offering, student, published_only
    )


def _source_sort_key(source: ComponentSourceResult):
    return (source.date is not None, source.date, getattr(source.source, "pk", 0))


def calculate_component_result(component, offering, student, *, published_only=True) -> ComponentResult:
    sources = component_sources(component, offering, student, published_only=published_only)
    completed = [source for source in sources if source.percentage is not None]
    completed.sort(key=_source_sort_key)
    if component.maximum_occurrences and len(completed) > component.maximum_occurrences:
        if component.aggregation_method == AssessmentWeightingComponent.BEST:
            completed = sorted(completed, key=lambda item: item.percentage or Decimal("0"), reverse=True)[
                : component.maximum_occurrences
            ]
        else:
            completed = completed[-component.maximum_occurrences :]
    if component.drop_lowest_count and len(completed) > component.drop_lowest_count:
        completed = sorted(completed, key=lambda item: item.percentage or Decimal("0"))[
            component.drop_lowest_count :
        ]
    pct = None
    if completed:
        if component.aggregation_method == AssessmentWeightingComponent.BEST:
            pct = max(item.percentage for item in completed if item.percentage is not None)
        elif component.aggregation_method == AssessmentWeightingComponent.LATEST:
            pct = max(completed, key=_source_sort_key).percentage
        else:
            values = [item.percentage for item in completed if item.percentage is not None]
            pct = quantize_percent(sum(values, Decimal("0")) / Decimal(len(values))) if values else None
    is_complete = len(completed) >= component.minimum_occurrences
    contribution = Decimal("0")
    if pct is not None:
        contribution = (pct * component.weight).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return ComponentResult(
        component=component,
        percentage=quantize_percent(pct),
        contribution=contribution,
        occurrence_count=len(sources),
        completed_count=len(completed),
        is_complete=is_complete,
        sources=sources,
    )


def calculate_scheme_result(scheme, offering, student, *, published_only=True) -> SchemeResult:
    errors = scheme_validation_errors(scheme)
    if errors:
        raise ValidationError(errors)
    component_results = [
        calculate_component_result(component, offering, student, published_only=published_only)
        for component in scheme.components.filter(is_active=True).select_related("assessment_type").order_by("order", "pk")
    ]
    missing_required = [
        result.component
        for result in component_results
        if result.component.is_required and not result.is_complete
    ]
    if scheme.missing_score_policy == AssessmentWeightingScheme.REQUIRE_COMPLETE and missing_required:
        return SchemeResult(
            scheme=scheme,
            percentage=None,
            contribution_total=sum((result.contribution for result in component_results), Decimal("0")),
            denominator_weight=scheme.total_weight,
            is_complete=False,
            missing_components=missing_required,
            components=component_results,
        )

    contribution_total = Decimal("0")
    denominator_weight = Decimal("0")
    for result in component_results:
        if result.percentage is not None:
            contribution_total += result.contribution
            denominator_weight += result.component.weight
        elif scheme.missing_score_policy == AssessmentWeightingScheme.ZERO_MISSING and result.component.is_required:
            denominator_weight += result.component.weight
        elif not scheme.normalize_to_total:
            denominator_weight += result.component.weight
    if not scheme.normalize_to_total:
        denominator_weight = scheme.total_weight
    result_percentage = None
    if denominator_weight > 0:
        result_percentage = quantize_percent(contribution_total / denominator_weight)
    return SchemeResult(
        scheme=scheme,
        percentage=result_percentage,
        contribution_total=contribution_total,
        denominator_weight=denominator_weight,
        is_complete=not missing_required,
        missing_components=missing_required,
        components=component_results,
    )


def build_course_result(
    offering: CourseOffering,
    assessments: list[Assessment],
    score_map: dict[int, AssessmentScore],
    *,
    student: StudentProfile | None = None,
) -> CourseResult:
    assessment_rows = []
    weighted_total = Decimal("0")
    total_weight = Decimal("0")
    simple_total = Decimal("0")
    completed_count = 0

    for assessment in assessments:
        score_obj = score_map.get(assessment.id)
        result = score_result(assessment, score_obj)
        if result.percentage is not None:
            completed_count += 1
            simple_total += result.percentage
            weight = _to_decimal(assessment.weight)
            if weight is not None and weight > 0:
                total_weight += weight
                weighted_total += result.percentage * weight
        assessment_rows.append({"assessment": assessment, "score": score_obj, "result": result})

    assessment_count = len(assessments)
    legacy_weighted = quantize_percent(weighted_total / total_weight) if total_weight > 0 else None
    simple_percentage = (
        quantize_percent(simple_total / Decimal(completed_count)) if completed_count > 0 else None
    )

    scheme = resolve_weighting_scheme(offering)
    scheme_result = None
    if scheme:
        resolved_student = student or next((score.student for score in score_map.values()), None)
        if resolved_student is not None:
            scheme_result = calculate_scheme_result(scheme, offering, resolved_student)

    weighted_percentage = scheme_result.percentage if scheme_result else (None if scheme else legacy_weighted)
    final_percentage = weighted_percentage if weighted_percentage is not None else (
        None if scheme else simple_percentage
    )
    if scheme_result:
        completed_count = sum(item.completed_count for item in scheme_result.components)
        assessment_count = sum(item.occurrence_count for item in scheme_result.components)
    grade, remark = grade_for_percentage(final_percentage)
    return CourseResult(
        offering=offering,
        assessments=assessment_rows,
        total_weight=scheme.total_weight if scheme else total_weight,
        weighted_percentage=weighted_percentage,
        simple_percentage=simple_percentage,
        grade=grade,
        remark=remark,
        completed_count=completed_count,
        assessment_count=assessment_count,
        scheme=scheme,
        is_complete=scheme_result.is_complete if scheme_result else not bool(scheme),
        component_results=scheme_result.components if scheme_result else [],
    )


def build_course_result_for_student(offering: CourseOffering, student: StudentProfile) -> CourseResult:
    assessments = list(
        Assessment.objects.filter(offering=offering, is_published=True)
        .select_related("assessment_type", "weighting_component")
        .order_by("date", "pk")
    )
    return build_course_result(
        offering, assessments, score_map_for_student(student, assessments), student=student
    )


def build_report_card(student: StudentProfile) -> ReportCard:
    assessments = list(published_assessments_for_student(student))
    score_map = score_map_for_student(student, assessments)
    offerings = {assessment.offering_id: assessment.offering for assessment in assessments}
    by_offering: dict[int, list[Assessment]] = {}
    for assessment in assessments:
        by_offering.setdefault(assessment.offering_id, []).append(assessment)
    try:
        from apps.tenant.exams.models import ExamPaper

        exam_offering_ids = ExamPaper.objects.filter(
            offering__in=active_offerings_for_student(student),
        ).filter(Q(results_published=True) | Q(show_results_immediately=True)).values_list("offering_id", flat=True)
        for offering in active_offerings_for_student(student).filter(pk__in=exam_offering_ids):
            offerings[offering.pk] = offering
            by_offering.setdefault(offering.pk, [])
    except Exception:
        pass

    course_results = [
        build_course_result(offerings[offering_id], items, score_map, student=student)
        for offering_id, items in by_offering.items()
    ]
    completed_course_percentages = []
    for result in course_results:
        if result.scheme:
            value = result.weighted_percentage
        else:
            value = result.weighted_percentage if result.weighted_percentage is not None else result.simple_percentage
        if value is not None:
            completed_course_percentages.append(value)
    overall_percentage = None
    if completed_course_percentages:
        overall_percentage = quantize_percent(
            sum(completed_course_percentages, Decimal("0")) / Decimal(len(completed_course_percentages))
        )
    overall_grade, overall_remark = grade_for_percentage(overall_percentage)
    return ReportCard(
        student=student,
        course_results=course_results,
        overall_percentage=overall_percentage,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        published_assessment_count=sum(result.assessment_count for result in course_results),
        completed_assessment_count=sum(result.completed_count for result in course_results),
    )


def assessment_framework_readiness() -> dict:
    schemes = list(AssessmentWeightingScheme.objects.prefetch_related("components__assessment_type"))
    invalid = []
    for scheme in schemes:
        errors = scheme_validation_errors(scheme)
        if errors:
            invalid.append({"scheme": scheme, "errors": errors})
    inactive_assessment_links = Assessment.objects.filter(
        Q(assessment_type__is_active=False)
        | Q(weighting_component__is_active=False)
        | Q(weighting_component__scheme__is_active=False)
    ).distinct().count()
    mismatched_assessment_links = Assessment.objects.filter(
        assessment_type__isnull=False,
        weighting_component__isnull=False,
    ).exclude(assessment_type_id=F("weighting_component__assessment_type_id")).count()
    classified = Assessment.objects.filter(assessment_type__isnull=False).count()
    total_assessments = Assessment.objects.count()
    checks = {
        "types_available": AssessmentType.objects.filter(is_active=True).exists(),
        "schemes_valid": not invalid,
        "links_active": inactive_assessment_links == 0,
        "links_consistent": mismatched_assessment_links == 0,
    }
    return {
        "checks": checks,
        "ready": all(checks.values()),
        "scheme_count": len(schemes),
        "invalid_schemes": invalid,
        "invalid_scheme_count": len(invalid),
        "inactive_link_count": inactive_assessment_links,
        "mismatched_link_count": mismatched_assessment_links,
        "assessment_count": total_assessments,
        "classified_assessment_count": classified,
        "unclassified_assessment_count": max(total_assessments - classified, 0),
    }


def parent_can_access_student(parent: ParentProfile, student: StudentProfile) -> bool:
    return ParentStudentLink.objects.filter(parent=parent, student=student).exists()


def parent_linked_students(parent: ParentProfile):
    return StudentProfile.objects.filter(parentstudentlink__parent=parent).select_related(
        "campus", "stream", "stream__class_group"
    ).distinct().order_by("last_name", "first_name")
