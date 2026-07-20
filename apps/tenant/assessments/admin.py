from django.contrib import admin

from .models import (
    Assessment,
    AssessmentScore,
    AssessmentType,
    AssessmentWeightingComponent,
    AssessmentWeightingScheme,
)


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
    list_filter = ("is_active", "is_default", "missing_score_policy", "campus", "stage")
    search_fields = ("code", "name", "description")
    autocomplete_fields = ("campus", "stage", "academic_term", "program")
    inlines = (AssessmentWeightingComponentInline,)


@admin.register(AssessmentWeightingComponent)
class AssessmentWeightingComponentAdmin(admin.ModelAdmin):
    list_display = ("scheme", "assessment_type", "weight", "aggregation_method", "is_required", "is_active")
    list_filter = ("aggregation_method", "is_required", "is_active")
    search_fields = ("scheme__code", "scheme__name", "assessment_type__code", "assessment_type__name")
    autocomplete_fields = ("scheme", "assessment_type")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("name", "offering", "assessment_type", "weighting_component", "max_score", "weight", "is_published")
    list_filter = ("is_published", "assessment_type")
    search_fields = ("name", "offering__course__name")
    autocomplete_fields = ("offering", "assessment_type", "weighting_component")


@admin.register(AssessmentScore)
class AssessmentScoreAdmin(admin.ModelAdmin):
    list_display = ("student", "assessment", "score", "graded_by", "graded_at")
    search_fields = ("student__first_name", "student__last_name", "assessment__name")
    autocomplete_fields = ("assessment", "student", "graded_by")
