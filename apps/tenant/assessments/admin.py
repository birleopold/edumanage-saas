from django.contrib import admin

from .models import (
    Assessment,
    AssessmentScore,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
    GradingProfile,
    ReportRule,
)
from .policy_models import AssessmentPolicy, AssessmentScorePolicy


@admin.register(AssessmentType)
class AssessmentTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "is_system", "is_active")
    list_filter = ("kind", "is_system", "is_active")
    search_fields = ("code", "name", "description")
    ordering = ("kind", "name")
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return ("code", "is_system") if obj and obj.is_system else ()

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


class AssessmentWeightingComponentInline(admin.TabularInline):
    model = AssessmentWeightingComponent
    extra = 0
    autocomplete_fields = ("assessment_type",)


@admin.register(AssessmentWeightingScheme)
class AssessmentWeightingSchemeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "campus",
        "stage",
        "academic_term",
        "program",
        "priority",
        "is_active",
    )
    list_filter = (
        "is_active",
        "is_default",
        "missing_score_policy",
        "campus",
        "stage",
    )
    search_fields = ("code", "name", "description")
    raw_id_fields = ("campus", "stage", "academic_term", "program")
    inlines = (AssessmentWeightingComponentInline,)


@admin.register(AssessmentWeightingComponent)
class AssessmentWeightingComponentAdmin(admin.ModelAdmin):
    list_display = (
        "scheme",
        "assessment_type",
        "weight",
        "aggregation_method",
        "is_required",
        "is_active",
    )
    list_filter = ("aggregation_method", "is_required", "is_active")
    search_fields = (
        "scheme__code",
        "scheme__name",
        "assessment_type__code",
        "assessment_type__name",
    )
    autocomplete_fields = ("scheme", "assessment_type")


class AssessmentPolicyInline(admin.StackedInline):
    model = AssessmentPolicy
    fk_name = "assessment"
    extra = 0
    max_num = 1
    can_delete = False
    raw_id_fields = ("responsible_teacher", "makeup_for")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "offering",
        "assessment_type",
        "weighting_component",
        "max_score",
        "weight",
        "is_published",
    )
    list_filter = ("is_published", "assessment_type")
    search_fields = ("name", "offering__course__name")
    raw_id_fields = ("offering", "assessment_type", "weighting_component")
    inlines = (AssessmentPolicyInline,)


class AssessmentScorePolicyInline(admin.StackedInline):
    model = AssessmentScorePolicy
    fk_name = "score_record"
    extra = 0
    max_num = 1
    can_delete = False
    raw_id_fields = ("makeup_completed_by",)


@admin.register(AssessmentScore)
class AssessmentScoreAdmin(admin.ModelAdmin):
    list_display = ("student", "assessment", "score", "graded_by", "graded_at")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "assessment__name",
    )
    raw_id_fields = ("assessment", "student", "graded_by")
    inlines = (AssessmentScorePolicyInline,)


@admin.register(AssessmentPolicy)
class AssessmentPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "assessment",
        "grading_mode",
        "absence_policy",
        "show_on_report",
        "allow_makeup",
        "responsible_teacher",
    )
    list_filter = (
        "grading_mode",
        "absence_policy",
        "show_on_report",
        "allow_makeup",
    )
    search_fields = (
        "assessment__name",
        "assessment__offering__course__name",
        "competency_framework_key",
    )
    raw_id_fields = ("assessment", "responsible_teacher", "makeup_for")


@admin.register(AssessmentScorePolicy)
class AssessmentScorePolicyAdmin(admin.ModelAdmin):
    list_display = (
        "score_record",
        "attendance_status",
        "competency_rating",
        "deferred_until",
        "makeup_completed_by",
    )
    list_filter = ("attendance_status", "competency_rating")
    search_fields = (
        "score_record__student__first_name",
        "score_record__student__last_name",
        "score_record__assessment__name",
    )
    raw_id_fields = ("score_record", "makeup_completed_by")


@admin.register(GradingProfile)
class GradingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "grading_scale",
        "campus",
        "stage",
        "level",
        "program",
        "academic_term",
        "priority",
        "is_active",
    )
    list_filter = (
        "is_active",
        "is_default",
        "overall_aggregation",
        "incomplete_result_policy",
        "campus",
        "stage",
    )
    search_fields = ("code", "name", "description", "grading_scale__name")
    raw_id_fields = (
        "grading_scale",
        "campus",
        "stage",
        "level",
        "program",
        "academic_term",
    )


@admin.register(ReportRule)
class ReportRuleAdmin(admin.ModelAdmin):
    list_display = (
        "grading_profile",
        "report_title",
        "show_percentage",
        "show_grade",
        "show_remark",
        "show_promotion_status",
    )
    list_filter = (
        "show_percentage",
        "show_grade",
        "show_remark",
        "show_promotion_status",
    )
    search_fields = ("grading_profile__code", "grading_profile__name", "report_title")
