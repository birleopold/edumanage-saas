from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import (
    Assignment,
    AssignmentSubmission,
    CourseworkComment,
    CourseworkProgress,
    LearningActivity,
    LearningMaterial,
)
from .services import visible_assignments_for_student, visible_materials_for_student


MATERIAL_KIND_MAP = {
    LearningMaterial.HOMEWORK: LearningActivity.ASSIGNMENT,
    LearningMaterial.NOTES: LearningActivity.RESOURCE,
    LearningMaterial.HOLIDAY_PACKAGE: LearningActivity.RESOURCE,
    LearningMaterial.VIDEO_LESSON: LearningActivity.VIDEO,
    LearningMaterial.LIVE_CLASS: LearningActivity.LIVE_CLASS,
}

ASSIGNMENT_KEYWORDS = (
    (LearningActivity.PROJECT, ("project", "portfolio", "research")),
    (LearningActivity.PRACTICAL, ("practical", "experiment", "laboratory", "lab ", "fieldwork")),
    (LearningActivity.DISCUSSION, ("discussion", "debate", "forum", "reflection")),
    (LearningActivity.QUIZ, ("quiz", "short test", "checkpoint")),
)


@dataclass(frozen=True)
class ActivitySyncResult:
    activity: LearningActivity | None
    created: bool = False
    updated: bool = False
    linked_records: int = 0


def classify_learning_source(source) -> str:
    if isinstance(source, LearningMaterial):
        return MATERIAL_KIND_MAP.get(source.type, LearningActivity.RESOURCE)
    text = f"{getattr(source, 'title', '')} {getattr(source, 'instructions', '')}".lower()
    for kind, keywords in ASSIGNMENT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return kind
    return LearningActivity.ASSIGNMENT


def activity_policy_defaults(source, kind: str | None = None) -> dict:
    kind = kind or classify_learning_source(source)
    if isinstance(source, Assignment):
        return {
            "completion_policy": LearningActivity.COMPLETION_SUBMISSION,
            "submission_policy": LearningActivity.SUBMISSION_REQUIRED,
        }
    if kind == LearningActivity.LIVE_CLASS:
        return {
            "completion_policy": LearningActivity.COMPLETION_MANUAL,
            "submission_policy": LearningActivity.SUBMISSION_NONE,
        }
    return {
        "completion_policy": LearningActivity.COMPLETION_VIEW,
        "submission_policy": LearningActivity.SUBMISSION_NONE,
    }


def learning_activity_for_source(source) -> LearningActivity | None:
    if source is None or not getattr(source, "pk", None):
        return None
    if isinstance(source, LearningMaterial):
        return LearningActivity.objects.filter(material=source).first()
    if isinstance(source, Assignment):
        return LearningActivity.objects.filter(assignment=source).first()
    return None


def _link_source_metadata(activity: LearningActivity) -> int:
    linked = 0
    if activity.material_id:
        linked += CourseworkComment.objects.filter(material_id=activity.material_id, activity__isnull=True).update(activity=activity)
        linked += CourseworkProgress.objects.filter(material_id=activity.material_id, activity__isnull=True).update(activity=activity)
    if activity.assignment_id:
        linked += CourseworkComment.objects.filter(assignment_id=activity.assignment_id, activity__isnull=True).update(activity=activity)
        linked += CourseworkProgress.objects.filter(assignment_id=activity.assignment_id, activity__isnull=True).update(activity=activity)
        linked += AssignmentSubmission.objects.filter(assignment_id=activity.assignment_id, activity__isnull=True).update(activity=activity)
    return linked


@transaction.atomic
def sync_learning_activity(source, *, refresh_policy: bool = False) -> ActivitySyncResult:
    if not isinstance(source, (LearningMaterial, Assignment)):
        raise TypeError("Learning activities can only be synchronized from LearningMaterial or Assignment records.")
    if not source.pk:
        raise ValueError("The source record must be saved before it can be synchronized.")

    kind = classify_learning_source(source)
    policy_defaults = activity_policy_defaults(source, kind)
    lookup = {"material": source, "assignment": None} if isinstance(source, LearningMaterial) else {"assignment": source, "material": None}
    activity = LearningActivity.objects.filter(**lookup).first()
    created = activity is None
    updated = False

    if created:
        activity = LearningActivity.objects.create(
            **lookup,
            kind=kind,
            title_snapshot=source.title,
            is_active=source.is_active,
            **policy_defaults,
        )
    else:
        update_fields = []
        if activity.title_snapshot != source.title:
            activity.title_snapshot = source.title
            update_fields.append("title_snapshot")
        if activity.is_active != source.is_active:
            activity.is_active = source.is_active
            update_fields.append("is_active")
        if refresh_policy and activity.kind != kind:
            activity.kind = kind
            update_fields.append("kind")
        if refresh_policy:
            for field, value in policy_defaults.items():
                if getattr(activity, field) != value:
                    setattr(activity, field, value)
                    update_fields.append(field)
        if update_fields:
            update_fields.append("updated_at")
            activity.save(update_fields=update_fields)
            updated = True

    linked_records = _link_source_metadata(activity)
    return ActivitySyncResult(activity=activity, created=created, updated=updated, linked_records=linked_records)


def preview_learning_activity_sync(*, refresh_policy: bool = False) -> dict:
    missing_materials = LearningMaterial.objects.exclude(pk__in=LearningActivity.objects.filter(material__isnull=False).values("material_id")).count()
    missing_assignments = Assignment.objects.exclude(pk__in=LearningActivity.objects.filter(assignment__isnull=False).values("assignment_id")).count()
    stale_titles = 0
    stale_status = 0
    reclassified = 0
    for activity in LearningActivity.objects.select_related("material", "assignment"):
        source = activity.source
        if source and activity.title_snapshot != source.title:
            stale_titles += 1
        if source and activity.is_active != source.is_active:
            stale_status += 1
        if refresh_policy and source and activity.kind != classify_learning_source(source):
            reclassified += 1
    unlinked = (
        AssignmentSubmission.objects.filter(activity__isnull=True).count()
        + CourseworkComment.objects.filter(activity__isnull=True).count()
        + CourseworkProgress.objects.filter(activity__isnull=True).count()
    )
    return {
        "materials_to_create": missing_materials,
        "assignments_to_create": missing_assignments,
        "stale_titles": stale_titles,
        "stale_status": stale_status,
        "activities_to_reclassify": reclassified,
        "metadata_links_to_add": unlinked,
    }


def sync_all_learning_activities(*, dry_run: bool = False, refresh_policy: bool = False) -> dict:
    if dry_run:
        return preview_learning_activity_sync(refresh_policy=refresh_policy)

    summary = {
        "materials_created": 0,
        "assignments_created": 0,
        "activities_updated": 0,
        "metadata_links_added": 0,
    }
    for material in LearningMaterial.objects.iterator():
        result = sync_learning_activity(material, refresh_policy=refresh_policy)
        summary["materials_created"] += int(result.created)
        summary["activities_updated"] += int(result.updated)
        summary["metadata_links_added"] += result.linked_records
    for assignment in Assignment.objects.iterator():
        result = sync_learning_activity(assignment, refresh_policy=refresh_policy)
        summary["assignments_created"] += int(result.created)
        summary["activities_updated"] += int(result.updated)
        summary["metadata_links_added"] += result.linked_records
    return summary


def visible_learning_activities_for_student(student, *, published_only: bool = True) -> list[LearningActivity]:
    material_ids = list(visible_materials_for_student(student, published_only=published_only).values_list("pk", flat=True))
    assignment_ids = list(visible_assignments_for_student(student, published_only=published_only).values_list("pk", flat=True))
    activities = list(
        LearningActivity.objects.filter(is_active=True)
        .filter(Q(material_id__in=material_ids) | Q(assignment_id__in=assignment_ids))
        .select_related("material", "assignment", "assessment_type", "weighting_component")
    )
    return sorted(
        activities,
        key=lambda item: (
            item.position,
            -(item.publish_at.timestamp() if item.publish_at else 0),
            item.pk,
        ),
    )


def activity_attachments(activity: LearningActivity):
    source = activity.source
    return source.attachments.all() if source else []


def activity_progress_for_student(activity: LearningActivity, student):
    progress = CourseworkProgress.objects.filter(activity=activity, student=student).order_by("-updated_at").first()
    if progress:
        return progress
    if activity.material_id:
        return CourseworkProgress.objects.filter(material_id=activity.material_id, student=student).order_by("-updated_at").first()
    return CourseworkProgress.objects.filter(assignment_id=activity.assignment_id, student=student).order_by("-updated_at").first()


def activity_submission_for_student(activity: LearningActivity, student):
    if not activity.assignment_id:
        return None
    return AssignmentSubmission.objects.filter(assignment_id=activity.assignment_id, student=student).first()


def unified_learner_progress_summary(student) -> dict:
    activities = visible_learning_activities_for_student(student)
    completed = 0
    pending_required = 0
    overdue = 0
    now = timezone.now()
    rows = []
    for activity in activities:
        progress = activity_progress_for_student(activity, student)
        submission = activity_submission_for_student(activity, student)
        is_complete = bool(progress and progress.completed_at)
        if activity.completion_policy == LearningActivity.COMPLETION_SUBMISSION:
            is_complete = bool(submission and submission.submitted_at)
        elif activity.completion_policy == LearningActivity.COMPLETION_SCORE:
            is_complete = bool(submission and submission.marked_at)
        if is_complete:
            completed += 1
        elif activity.submission_policy == LearningActivity.SUBMISSION_REQUIRED:
            pending_required += 1
        due_at = activity.due_at
        if isinstance(due_at, date) and not isinstance(due_at, datetime):
            due_at = timezone.make_aware(datetime.combine(due_at, time.max))
        if due_at and due_at < now and not is_complete:
            overdue += 1
        rows.append({"activity": activity, "progress": progress, "submission": submission, "is_complete": is_complete})
    total = len(rows)
    return {
        "student": student,
        "activities": rows,
        "total_items": total,
        "completed_items": completed,
        "completion_rate": round((completed / total) * 100, 1) if total else 0,
        "pending_required": pending_required,
        "overdue_items": overdue,
    }


def learning_activity_readiness() -> dict:
    material_count = LearningMaterial.objects.count()
    assignment_count = Assignment.objects.count()
    activity_count = LearningActivity.objects.count()
    linked_material_count = LearningActivity.objects.filter(material__isnull=False).count()
    linked_assignment_count = LearningActivity.objects.filter(assignment__isnull=False).count()
    missing_source_count = max(material_count - linked_material_count, 0) + max(assignment_count - linked_assignment_count, 0)
    stale_snapshot_count = 0
    for activity in LearningActivity.objects.select_related("material", "assignment"):
        source = activity.source
        if source and (activity.title_snapshot != source.title or activity.is_active != source.is_active):
            stale_snapshot_count += 1
    unlinked_submission_count = AssignmentSubmission.objects.filter(activity__isnull=True).count()
    unlinked_comment_count = CourseworkComment.objects.filter(activity__isnull=True).count()
    unlinked_progress_count = CourseworkProgress.objects.filter(activity__isnull=True).count()
    mismatched_submission_count = AssignmentSubmission.objects.filter(activity__isnull=False).exclude(
        assignment_id=F("activity__assignment_id")
    ).count()
    invalid_assessment_link_count = LearningActivity.objects.filter(
        assessment_type__isnull=False,
        weighting_component__isnull=False,
    ).exclude(assessment_type_id=F("weighting_component__assessment_type_id")).count()
    issues = (
        missing_source_count
        + stale_snapshot_count
        + unlinked_submission_count
        + unlinked_comment_count
        + unlinked_progress_count
        + mismatched_submission_count
        + invalid_assessment_link_count
    )
    return {
        "ready": issues == 0,
        "material_count": material_count,
        "assignment_count": assignment_count,
        "activity_count": activity_count,
        "missing_source_count": missing_source_count,
        "stale_snapshot_count": stale_snapshot_count,
        "unlinked_submission_count": unlinked_submission_count,
        "unlinked_comment_count": unlinked_comment_count,
        "unlinked_progress_count": unlinked_progress_count,
        "mismatched_submission_count": mismatched_submission_count,
        "invalid_assessment_link_count": invalid_assessment_link_count,
        "issue_count": issues,
    }
