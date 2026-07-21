from django.contrib import admin

from .external_models import (
    ExternalCandidate,
    ExternalCandidateSubject,
    ExternalExamBoard,
    ExternalExamCentre,
    ExternalExamResult,
    ExternalExamSession,
    ExternalExamSubject,
    ExternalResultImportBatch,
)


@admin.register(ExternalExamBoard)
class ExternalExamBoardAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "board_type", "country_code", "is_active")
    list_filter = ("board_type", "is_active", "country_code")
    search_fields = ("code", "name")


@admin.register(ExternalExamCentre)
class ExternalExamCentreAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "board", "campus", "is_active")
    list_filter = ("board", "campus", "is_active")
    search_fields = ("code", "name", "board__name")
    raw_id_fields = ("board", "campus")


@admin.register(ExternalExamSession)
class ExternalExamSessionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "board", "academic_year", "campus", "status", "is_active")
    list_filter = ("board", "academic_year", "campus", "status", "is_active")
    search_fields = ("code", "name", "board__name")
    raw_id_fields = ("board", "centre", "academic_year", "campus", "stage", "level", "program", "linked_exam")


@admin.register(ExternalExamSubject)
class ExternalExamSubjectAdmin(admin.ModelAdmin):
    list_display = ("subject_code", "course", "session", "is_compulsory", "linked_paper", "is_active")
    list_filter = ("session__board", "session", "is_compulsory", "is_active")
    search_fields = ("subject_code", "display_name", "course__name", "session__name")
    raw_id_fields = ("session", "course", "linked_paper")


class ExternalCandidateSubjectInline(admin.TabularInline):
    model = ExternalCandidateSubject
    extra = 0
    raw_id_fields = ("subject",)


@admin.register(ExternalCandidate)
class ExternalCandidateAdmin(admin.ModelAdmin):
    list_display = ("candidate_number", "student", "session", "centre", "status", "is_active")
    list_filter = ("session__board", "session", "centre", "status", "is_active")
    search_fields = ("candidate_number", "student__first_name", "student__last_name", "student__student_id")
    raw_id_fields = ("session", "student", "centre")
    inlines = (ExternalCandidateSubjectInline,)


@admin.register(ExternalCandidateSubject)
class ExternalCandidateSubjectAdmin(admin.ModelAdmin):
    list_display = ("candidate", "subject", "status", "paper_reference", "registered_at")
    list_filter = ("candidate__session", "status")
    search_fields = ("candidate__candidate_number", "subject__subject_code", "subject__course__name")
    raw_id_fields = ("candidate", "subject")


@admin.register(ExternalExamResult)
class ExternalExamResultAdmin(admin.ModelAdmin):
    list_display = ("candidate_subject", "score", "percentage", "grade", "result_status", "is_official", "released_at")
    list_filter = ("candidate_subject__candidate__session", "result_status", "is_official")
    search_fields = ("candidate_subject__candidate__candidate_number", "candidate_subject__subject__subject_code", "source_reference")
    raw_id_fields = ("candidate_subject", "linked_exam_score", "imported_by")


@admin.register(ExternalResultImportBatch)
class ExternalResultImportBatchAdmin(admin.ModelAdmin):
    list_display = ("session", "file_name", "dry_run", "row_count", "accepted_count", "rejected_count", "created_at")
    list_filter = ("session__board", "session", "dry_run", "created_at")
    search_fields = ("file_name", "session__code", "session__name")
    raw_id_fields = ("session", "imported_by")
    readonly_fields = ("errors", "created_at")
