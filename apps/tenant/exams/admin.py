from django.contrib import admin

from .models import (
    Exam,
    ExamAnalytics,
    ExamAntiCheatEvent,
    ExamPaper,
    ExamQuestion,
    ExamSchedule,
    ExamScore,
    OnlineExamAttempt,
    QuestionBank,
    SeatAllocation,
    StudentResponse,
)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("name", "term", "exam_mode", "start_date", "end_date", "is_active")
    list_filter = ("exam_mode", "is_active", "term")
    search_fields = ("name", "description")
    date_hierarchy = "start_date"


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ("exam", "offering", "assessment_type", "weighting_component", "max_score", "passing_score", "date", "is_published", "results_published", "report_cards_enabled")
    list_filter = ("is_published", "results_published", "report_cards_enabled", "assessment_type", "exam__exam_mode", "randomize_questions")
    search_fields = ("exam__name", "offering__course__name")
    raw_id_fields = ("exam", "offering", "assessment_type", "weighting_component", "linked_assessment")
    date_hierarchy = "date"


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ("get_question_preview", "course", "question_type", "difficulty", "marks", "is_active", "created_by")
    list_filter = ("question_type", "difficulty", "is_active", "course")
    search_fields = ("question_text", "tags")
    raw_id_fields = ("course", "created_by")
    date_hierarchy = "created_at"

    def get_question_preview(self, obj):
        return obj.question_text[:80] + "..." if len(obj.question_text) > 80 else obj.question_text
    get_question_preview.short_description = "Question"


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ("paper", "question", "order", "marks")
    list_filter = ("paper__exam", "question__question_type")
    search_fields = ("paper__exam__name", "question__question_text")
    raw_id_fields = ("paper", "question")
    ordering = ("paper", "order")


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = ("paper", "room_name", "date", "start_time", "end_time", "capacity", "get_allocated", "invigilator")
    list_filter = ("date", "invigilator")
    search_fields = ("paper__exam__name", "room_name")
    raw_id_fields = ("paper", "invigilator")
    date_hierarchy = "date"

    def get_allocated(self, obj):
        return f"{obj.allocated_seats()}/{obj.capacity}"
    get_allocated.short_description = "Seats Allocated"


@admin.register(SeatAllocation)
class SeatAllocationAdmin(admin.ModelAdmin):
    list_display = ("student", "schedule", "seat_number", "admit_card_generated", "admit_card_generated_at")
    list_filter = ("admit_card_generated", "schedule__date")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "seat_number")
    raw_id_fields = ("schedule", "student")
    date_hierarchy = "admit_card_generated_at"


class StudentResponseInline(admin.TabularInline):
    model = StudentResponse
    extra = 0
    readonly_fields = ("answered_at",)


@admin.register(OnlineExamAttempt)
class OnlineExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "paper", "status", "started_at", "submitted_at", "score", "browser_focus_warnings", "ip_address")
    list_filter = ("status", "paper__exam")
    search_fields = ("student__first_name", "student__last_name", "student__student_id")
    raw_id_fields = ("paper", "student")
    date_hierarchy = "started_at"
    ordering = ("-started_at",)
    readonly_fields = ("question_order", "user_agent", "last_activity_at", "locked_at", "locked_reason")
    inlines = (StudentResponseInline,)


@admin.register(StudentResponse)
class StudentResponseAdmin(admin.ModelAdmin):
    list_display = ("attempt", "exam_question", "is_correct", "marks_awarded", "manually_marked_by", "answered_at")
    list_filter = ("is_correct", "exam_question__question__question_type")
    search_fields = ("attempt__student__first_name", "attempt__student__last_name")
    raw_id_fields = ("attempt", "exam_question", "manually_marked_by")
    ordering = ("attempt", "exam_question__order")


@admin.register(ExamAntiCheatEvent)
class ExamAntiCheatEventAdmin(admin.ModelAdmin):
    list_display = ("attempt", "event_type", "ip_address", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("attempt__student__first_name", "attempt__student__last_name", "attempt__student__student_id")
    raw_id_fields = ("attempt",)
    readonly_fields = ("metadata", "created_at")


@admin.register(ExamScore)
class ExamScoreAdmin(admin.ModelAdmin):
    list_display = ("student", "paper", "score", "percentage", "grade", "rank", "graded_by", "graded_at")
    list_filter = ("paper__exam", "grade")
    search_fields = ("student__first_name", "student__last_name", "student__student_id")
    raw_id_fields = ("paper", "student", "graded_by")
    date_hierarchy = "graded_at"


@admin.register(ExamAnalytics)
class ExamAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("paper", "total_students", "appeared_students", "average_score", "pass_rate", "updated_at")
    list_filter = ("paper__exam",)
    search_fields = ("paper__exam__name", "paper__offering__course__name")
    raw_id_fields = ("paper",)
    date_hierarchy = "updated_at"
    readonly_fields = ("updated_at",)
