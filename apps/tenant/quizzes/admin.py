from django.contrib import admin

from .models import (
    Quiz,
    QuizQuestion,
    QuizQuestionChoice,
    QuizAttempt,
    QuizAnswer,
)


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0
    fields = ('question_text', 'question_type', 'points', 'order')


class QuizQuestionChoiceInline(admin.TabularInline):
    model = QuizQuestionChoice
    extra = 4
    fields = ('choice_text', 'is_correct', 'order')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_offering', 'campus', 'difficulty', 'is_active', 'created_at')
    list_filter = ('is_active', 'difficulty', 'campus', 'created_at')
    search_fields = ('name', 'topic', 'description')
    filter_horizontal = ('students',)
    inlines = [QuizQuestionInline]
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'name', 'topic', 'description')
        }),
        ('Relations', {
            'fields': ('campus', 'course_offering', 'created_by')
        }),
        ('Settings', {
            'fields': ('time_limit_minutes', 'show_one_question_at_time', 'passing_score_percentage', 'difficulty')
        }),
        ('Availability', {
            'fields': ('is_active', 'available_from', 'available_until', 'students')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'question_text_short', 'question_type', 'points', 'order')
    list_filter = ('question_type', 'quiz')
    search_fields = ('question_text',)
    inlines = [QuizQuestionChoiceInline]
    
    def question_text_short(self, obj):
        return obj.question_text[:50]
    question_text_short.short_description = 'Question'


@admin.register(QuizQuestionChoice)
class QuizQuestionChoiceAdmin(admin.ModelAdmin):
    list_display = ('question', 'choice_text', 'is_correct', 'order')
    list_filter = ('is_correct', 'question__quiz')
    search_fields = ('choice_text',)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'status', 'score', 'percentage', 'passed', 'started_at')
    list_filter = ('status', 'passed', 'quiz', 'started_at')
    search_fields = ('student__first_name', 'student__last_name', 'quiz__name')
    readonly_fields = ('started_at', 'completed_at', 'graded_at')
    
    fieldsets = (
        ('Attempt Info', {
            'fields': ('quiz', 'student', 'status')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at')
        }),
        ('Scoring', {
            'fields': ('score', 'max_score', 'percentage', 'passed')
        }),
        ('Grading', {
            'fields': ('graded_by', 'graded_at', 'feedback')
        }),
    )


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct', 'points_earned', 'answered_at')
    list_filter = ('is_correct', 'attempt__quiz')
    search_fields = ('answer_text',)
    readonly_fields = ('answered_at',)
