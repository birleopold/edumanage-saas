from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.tenant.academics.models import Enrollment

from .models import Assignment, AssignmentSubmission, CourseworkProgress, LearningMaterial


def active_offering_ids_for_student(student) -> list[int]:
    return list(Enrollment.objects.filter(student=student, status=Enrollment.ACTIVE).values_list("offering_id", flat=True))


def student_class_group(student):
    return getattr(student.stream, "class_group", None) if getattr(student, "stream", None) else None


def _student_visibility_filter(qs: QuerySet, student, offering_ids: list[int] | None = None) -> QuerySet:
    offering_ids = active_offering_ids_for_student(student) if offering_ids is None else offering_ids
    class_group = student_class_group(student)
    return (
        qs.filter(Q(campus__isnull=True) | Q(campus=student.campus))
        .filter(Q(stream__isnull=True) | Q(stream=student.stream))
        .filter(Q(class_group__isnull=True) | Q(class_group=class_group))
        .filter(Q(offering__isnull=True) | Q(offering_id__in=offering_ids))
    )


def visible_materials_for_student(student, *, published_only: bool = True) -> QuerySet:
    qs = LearningMaterial.objects.select_related("campus", "class_group", "stream", "offering").prefetch_related("attachments", "comments")
    if published_only:
        qs = qs.filter(is_active=True, publish_at__lte=timezone.now())
    return _student_visibility_filter(qs, student)


def visible_assignments_for_student(student, *, published_only: bool = True) -> QuerySet:
    qs = Assignment.objects.select_related("campus", "class_group", "stream", "offering").prefetch_related("attachments", "comments")
    if published_only:
        qs = qs.filter(is_active=True, publish_at__lte=timezone.now())
    return _student_visibility_filter(qs, student)


def student_can_access_material(student, material: LearningMaterial) -> bool:
    return visible_materials_for_student(student).filter(pk=material.pk).exists()


def student_can_access_assignment(student, assignment: Assignment) -> bool:
    return visible_assignments_for_student(student).filter(pk=assignment.pk).exists()


def assignment_is_overdue(assignment: Assignment, *, now=None) -> bool:
    now = now or timezone.now()
    return bool(assignment.due_date and now > assignment.due_date)


def material_progress_for_student(student, material: LearningMaterial):
    progress, _created = CourseworkProgress.objects.get_or_create(student=student, material=material, assignment=None)
    return progress


def assignment_progress_for_student(student, assignment: Assignment):
    progress, _created = CourseworkProgress.objects.get_or_create(student=student, assignment=assignment, material=None)
    return progress


def mark_material_viewed(student, material: LearningMaterial):
    progress = material_progress_for_student(student, material)
    now = timezone.now()
    update_fields = ["viewed_at", "percent_complete", "updated_at"]
    progress.viewed_at = progress.viewed_at or now
    if progress.percent_complete < Decimal("50"):
        progress.percent_complete = Decimal("50")
    progress.save(update_fields=update_fields)
    return progress


def mark_material_completed(student, material: LearningMaterial):
    progress = material_progress_for_student(student, material)
    now = timezone.now()
    progress.viewed_at = progress.viewed_at or now
    progress.completed_at = progress.completed_at or now
    progress.percent_complete = Decimal("100")
    progress.save(update_fields=["viewed_at", "completed_at", "percent_complete", "updated_at"])
    return progress


def mark_assignment_viewed(student, assignment: Assignment):
    progress = assignment_progress_for_student(student, assignment)
    now = timezone.now()
    progress.viewed_at = progress.viewed_at or now
    if progress.percent_complete < Decimal("25"):
        progress.percent_complete = Decimal("25")
    progress.save(update_fields=["viewed_at", "percent_complete", "updated_at"])
    return progress


def mark_assignment_submitted(student, assignment: Assignment):
    progress = assignment_progress_for_student(student, assignment)
    now = timezone.now()
    progress.viewed_at = progress.viewed_at or now
    progress.completed_at = progress.completed_at or now
    progress.percent_complete = Decimal("100")
    progress.save(update_fields=["viewed_at", "completed_at", "percent_complete", "updated_at"])
    return progress


def attach_submission_status(assignments: list[Assignment], student) -> list[Assignment]:
    submissions = {
        s.assignment_id: s
        for s in AssignmentSubmission.objects.filter(student=student, assignment_id__in=[a.id for a in assignments]).prefetch_related("attachments")
    }
    progress_records = {
        p.assignment_id: p
        for p in CourseworkProgress.objects.filter(student=student, assignment_id__in=[a.id for a in assignments])
    }
    now = timezone.now()
    for assignment in assignments:
        assignment.submission = submissions.get(assignment.id)
        assignment.progress_record = progress_records.get(assignment.id)
        assignment.progress_percent = assignment.progress_record.percent_complete if assignment.progress_record else 0
        assignment.is_submitted = bool(assignment.submission and assignment.submission.submitted_at)
        assignment.is_marked = bool(assignment.submission and assignment.submission.marked_at)
        assignment.is_overdue = assignment_is_overdue(assignment, now=now)
    return assignments


def attach_material_progress(materials: list[LearningMaterial], student) -> list[LearningMaterial]:
    progress_records = {p.material_id: p for p in CourseworkProgress.objects.filter(student=student, material_id__in=[m.id for m in materials])}
    for material in materials:
        material.progress_record = progress_records.get(material.id)
        material.progress_percent = material.progress_record.percent_complete if material.progress_record else 0
        material.is_completed = bool(material.progress_record and material.progress_record.completed_at)
    return materials


def ensure_assignment_submission_rows(assignment: Assignment) -> int:
    """Create empty submission rows for all active enrolled students in an assignment offering."""
    if not assignment.offering_id:
        return 0
    enrollment_student_ids = list(Enrollment.objects.filter(offering_id=assignment.offering_id, status=Enrollment.ACTIVE).values_list("student_id", flat=True))
    if not enrollment_student_ids:
        return 0
    existing_student_ids = set(AssignmentSubmission.objects.filter(assignment=assignment, student_id__in=enrollment_student_ids).values_list("student_id", flat=True))
    missing_ids = [sid for sid in enrollment_student_ids if sid not in existing_student_ids]
    if not missing_ids:
        return 0
    AssignmentSubmission.objects.bulk_create([AssignmentSubmission(assignment=assignment, student_id=sid) for sid in missing_ids], ignore_conflicts=True)
    return len(missing_ids)


def submission_summary_for_assignment(assignment: Assignment) -> dict:
    qs = AssignmentSubmission.objects.filter(assignment=assignment)
    total = qs.count()
    submitted = qs.filter(submitted_at__isnull=False).count()
    marked = qs.filter(marked_at__isnull=False).count()
    pending = max(total - submitted, 0)
    return {
        "total": total,
        "submitted": submitted,
        "pending": pending,
        "marked": marked,
        "submission_rate": round((submitted / total) * 100, 1) if total else 0,
        "marking_rate": round((marked / submitted) * 100, 1) if submitted else 0,
    }


def learner_progress_summary(student) -> dict:
    assignments = list(visible_assignments_for_student(student).order_by("-publish_at")[:200])
    materials = list(visible_materials_for_student(student).order_by("-publish_at")[:200])
    attach_submission_status(assignments, student)
    attach_material_progress(materials, student)
    total_items = len(assignments) + len(materials)
    completed_items = sum(1 for assignment in assignments if assignment.is_submitted) + sum(1 for material in materials if material.is_completed)
    return {
        "student": student,
        "total_items": total_items,
        "completed_items": completed_items,
        "completion_rate": round((completed_items / total_items) * 100, 1) if total_items else 0,
        "pending_assignments": sum(1 for assignment in assignments if not assignment.is_submitted),
        "overdue_assignments": sum(1 for assignment in assignments if assignment.is_overdue and not assignment.is_submitted),
        "marked_assignments": sum(1 for assignment in assignments if assignment.is_marked),
    }
