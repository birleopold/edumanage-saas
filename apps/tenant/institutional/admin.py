from django.contrib import admin

from .academic_records import (
    AcademicAttemptPolicy,
    AcademicStanding,
    CourseAttempt,
    SemesterRegistration,
)
from .models import (
    CandidateDossier,
    CandidateExamAttendance,
    CandidateMockCycle,
    ECDObservation,
    LearnerSubjectCombination,
    MealAttendance,
    MealService,
    ReportTemplate,
    ResultPolicy,
    StudentProperty,
    VerifiablePermit,
    VisitationWindow,
    VisitorRecord,
)


for model in (
    ReportTemplate,
    ResultPolicy,
    ECDObservation,
    LearnerSubjectCombination,
    CandidateDossier,
    CandidateMockCycle,
    CandidateExamAttendance,
    VerifiablePermit,
    VisitationWindow,
    VisitorRecord,
    MealService,
    MealAttendance,
    StudentProperty,
):
    admin.site.register(model)


@admin.register(AcademicAttemptPolicy)
class AcademicAttemptPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "campus",
        "program",
        "level",
        "replacement_mode",
        "maximum_attempts",
        "probation_cgpa",
        "priority",
        "is_active",
    )
    list_filter = (
        "replacement_mode",
        "is_default",
        "is_active",
        "campus",
        "program",
        "level",
    )
    search_fields = ("name", "program__name", "level__name")
    raw_id_fields = ("campus", "program", "level")


class CourseAttemptInline(admin.TabularInline):
    model = CourseAttempt
    extra = 0
    raw_id_fields = (
        "course",
        "offering",
        "replaced_attempt",
        "registered_by",
        "approved_by",
    )


@admin.register(SemesterRegistration)
class SemesterRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "academic_term",
        "program",
        "status",
        "registration_reference",
        "registered_on",
        "approved_at",
    )
    list_filter = ("status", "academic_term", "program")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__student_id",
        "registration_reference",
    )
    raw_id_fields = (
        "student",
        "academic_term",
        "program",
        "registered_by",
        "approved_by",
    )
    inlines = (CourseAttemptInline,)


@admin.register(CourseAttempt)
class CourseAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "registration",
        "course",
        "attempt_number",
        "attempt_type",
        "status",
        "percentage",
        "grade",
        "grade_point",
        "credits",
        "counts_toward_gpa",
    )
    list_filter = (
        "attempt_type",
        "status",
        "counts_toward_gpa",
        "registration__academic_term",
    )
    search_fields = (
        "registration__student__first_name",
        "registration__student__last_name",
        "registration__student__student_id",
        "course__name",
        "course__code",
    )
    raw_id_fields = (
        "registration",
        "course",
        "offering",
        "replaced_attempt",
        "registered_by",
        "approved_by",
    )


@admin.register(AcademicStanding)
class AcademicStandingAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "academic_term",
        "semester_gpa",
        "cumulative_gpa",
        "attempted_credits",
        "earned_credits",
        "standing",
        "progression_decision",
        "calculated_at",
    )
    list_filter = ("standing", "academic_term")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__student_id",
        "progression_decision",
    )
    raw_id_fields = ("student", "academic_term", "calculated_by")
    readonly_fields = ("snapshot", "calculated_at")
