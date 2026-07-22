from django.contrib import admin

from .models import (
    Assignment,
    AssignmentAttachment,
    AssignmentSubmission,
    AssignmentSubmissionAttachment,
    CourseworkComment,
    CourseworkProgress,
    LearningActivity,
    LearningMaterial,
    LearningMaterialAttachment,
)
from .workflow_models import (
    AssignmentGroup,
    AssignmentGroupMember,
    GroupSubmission,
    GroupSubmissionAttachment,
    LearningActivityProfile,
    SubmissionWorkflow,
)


class LearningMaterialAttachmentInline(admin.TabularInline):
    model = LearningMaterialAttachment
    extra = 0


@admin.register(LearningMaterial)
class LearningMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "type",
        "offering",
        "class_group",
        "publish_at",
        "is_active",
        "allow_comments",
    )
    list_filter = ("type", "is_active", "allow_comments", "campus", "class_group")
    search_fields = ("title", "description")
    inlines = (LearningMaterialAttachmentInline,)


class AssignmentAttachmentInline(admin.TabularInline):
    model = AssignmentAttachment
    extra = 0


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "offering",
        "class_group",
        "publish_at",
        "due_date",
        "is_active",
        "allow_comments",
    )
    list_filter = ("is_active", "allow_comments", "campus", "class_group")
    search_fields = ("title", "instructions")
    inlines = (AssignmentAttachmentInline,)


class LearningActivityProfileInline(admin.StackedInline):
    model = LearningActivityProfile
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(LearningActivity)
class LearningActivityAdmin(admin.ModelAdmin):
    list_display = (
        "title_snapshot",
        "kind",
        "source_type",
        "position",
        "completion_policy",
        "submission_policy",
        "assessment_type",
        "is_active",
    )
    list_filter = ("kind", "completion_policy", "submission_policy", "is_active")
    search_fields = ("title_snapshot", "material__title", "assignment__title")
    raw_id_fields = (
        "material",
        "assignment",
        "assessment_type",
        "weighting_component",
    )
    readonly_fields = ("uuid", "title_snapshot", "created_at", "updated_at")
    inlines = (LearningActivityProfileInline,)

    def has_add_permission(self, request):
        return False


class AssignmentSubmissionAttachmentInline(admin.TabularInline):
    model = AssignmentSubmissionAttachment
    extra = 0


class SubmissionWorkflowInline(admin.StackedInline):
    model = SubmissionWorkflow
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "assignment",
        "student",
        "activity",
        "submitted_at",
        "score",
        "marked_at",
        "marked_by",
    )
    list_filter = ("submitted_at", "marked_at")
    search_fields = (
        "assignment__title",
        "student__first_name",
        "student__last_name",
        "student__student_id",
    )
    raw_id_fields = ("activity",)
    inlines = (AssignmentSubmissionAttachmentInline, SubmissionWorkflowInline)


@admin.register(LearningActivityProfile)
class LearningActivityProfileAdmin(admin.ModelAdmin):
    list_display = (
        "activity",
        "detailed_kind",
        "group_work",
        "resubmission_allowed",
        "maximum_attempts",
        "competency_tracking",
    )
    list_filter = (
        "detailed_kind",
        "group_work",
        "resubmission_allowed",
        "competency_tracking",
    )
    search_fields = (
        "activity__title_snapshot",
        "competency_framework_key",
    )
    raw_id_fields = ("activity",)


class AssignmentGroupMemberInline(admin.TabularInline):
    model = AssignmentGroupMember
    extra = 0
    raw_id_fields = ("student",)


@admin.register(AssignmentGroup)
class AssignmentGroupAdmin(admin.ModelAdmin):
    list_display = ("activity", "name", "capacity", "is_active", "created_by")
    list_filter = ("is_active",)
    search_fields = ("name", "activity__title_snapshot")
    raw_id_fields = ("activity", "created_by")
    inlines = (AssignmentGroupMemberInline,)


@admin.register(AssignmentGroupMember)
class AssignmentGroupMemberAdmin(admin.ModelAdmin):
    list_display = ("group", "student", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active")
    search_fields = (
        "group__name",
        "student__first_name",
        "student__last_name",
        "student__student_id",
    )
    raw_id_fields = ("group", "student")


class GroupSubmissionAttachmentInline(admin.TabularInline):
    model = GroupSubmissionAttachment
    extra = 0


@admin.register(GroupSubmission)
class GroupSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "activity",
        "group",
        "status",
        "attempt_count",
        "submitted_at",
        "is_late",
        "score",
        "marked_at",
    )
    list_filter = ("status", "is_late", "late_excused", "competency_rating")
    search_fields = (
        "activity__title_snapshot",
        "group__name",
    )
    raw_id_fields = ("activity", "group", "submitted_by", "marked_by")
    inlines = (GroupSubmissionAttachmentInline,)


@admin.register(SubmissionWorkflow)
class SubmissionWorkflowAdmin(admin.ModelAdmin):
    list_display = (
        "submission",
        "status",
        "attempt_count",
        "is_late",
        "late_excused",
        "competency_rating",
        "updated_at",
    )
    list_filter = (
        "status",
        "is_late",
        "late_excused",
        "competency_rating",
    )
    search_fields = (
        "submission__assignment__title",
        "submission__student__first_name",
        "submission__student__last_name",
    )
    raw_id_fields = ("submission",)


@admin.register(CourseworkComment)
class CourseworkCommentAdmin(admin.ModelAdmin):
    list_display = (
        "material",
        "assignment",
        "activity",
        "user",
        "is_teacher_reply",
        "created_at",
    )
    list_filter = ("is_teacher_reply", "created_at")
    search_fields = ("body", "material__title", "assignment__title")
    raw_id_fields = ("activity",)


@admin.register(CourseworkProgress)
class CourseworkProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "material",
        "assignment",
        "activity",
        "percent_complete",
        "viewed_at",
        "completed_at",
        "updated_at",
    )
    list_filter = ("completed_at", "updated_at")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__student_id",
        "material__title",
        "assignment__title",
    )
    raw_id_fields = ("activity",)
