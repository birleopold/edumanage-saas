from django.contrib import admin

from .models import (
    Assignment,
    AssignmentAttachment,
    AssignmentSubmission,
    AssignmentSubmissionAttachment,
    CourseworkComment,
    CourseworkProgress,
    LearningMaterial,
    LearningMaterialAttachment,
)


class LearningMaterialAttachmentInline(admin.TabularInline):
    model = LearningMaterialAttachment
    extra = 0


@admin.register(LearningMaterial)
class LearningMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "offering", "class_group", "publish_at", "is_active", "allow_comments")
    list_filter = ("type", "is_active", "allow_comments", "campus", "class_group")
    search_fields = ("title", "description")
    inlines = (LearningMaterialAttachmentInline,)


class AssignmentAttachmentInline(admin.TabularInline):
    model = AssignmentAttachment
    extra = 0


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "offering", "class_group", "publish_at", "due_date", "is_active", "allow_comments")
    list_filter = ("is_active", "allow_comments", "campus", "class_group")
    search_fields = ("title", "instructions")
    inlines = (AssignmentAttachmentInline,)


class AssignmentSubmissionAttachmentInline(admin.TabularInline):
    model = AssignmentSubmissionAttachment
    extra = 0


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "submitted_at", "score", "marked_at", "marked_by")
    list_filter = ("submitted_at", "marked_at")
    search_fields = ("assignment__title", "student__first_name", "student__last_name", "student__student_id")
    inlines = (AssignmentSubmissionAttachmentInline,)


@admin.register(CourseworkComment)
class CourseworkCommentAdmin(admin.ModelAdmin):
    list_display = ("material", "assignment", "user", "is_teacher_reply", "created_at")
    list_filter = ("is_teacher_reply", "created_at")
    search_fields = ("body", "material__title", "assignment__title")


@admin.register(CourseworkProgress)
class CourseworkProgressAdmin(admin.ModelAdmin):
    list_display = ("student", "material", "assignment", "percent_complete", "viewed_at", "completed_at", "updated_at")
    list_filter = ("completed_at", "updated_at")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "material__title", "assignment__title")
