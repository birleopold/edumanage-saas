from django.contrib import admin

from .models import (
    AcademicFramework,
    CampusEducationStage,
    EducationStage,
    FrameworkStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)


@admin.register(EducationStage)
class EducationStageAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "local_name",
        "default_period_type",
        "is_system",
        "is_active",
    )
    list_filter = ("default_period_type", "is_system", "is_active")
    search_fields = ("code", "name", "local_name")
    ordering = ("order", "name")
    actions = None

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_system:
            return ("code", "is_system")
        return ()

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


class FrameworkStageInline(admin.TabularInline):
    model = FrameworkStage
    extra = 0
    autocomplete_fields = ("stage",)
    can_delete = False

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_system_template:
            return ("stage",)
        return ()


@admin.register(AcademicFramework)
class AcademicFrameworkAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "country_code",
        "is_system_template",
        "is_active",
    )
    list_filter = ("country_code", "is_system_template", "is_active")
    search_fields = ("code", "name", "description")
    inlines = (FrameworkStageInline,)
    actions = None

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_system_template:
            return ("code", "is_system_template")
        return ()

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system_template:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(FrameworkStage)
class FrameworkStageAdmin(admin.ModelAdmin):
    list_display = (
        "framework",
        "stage",
        "local_name",
        "period_label",
        "candidate_class",
        "is_active",
    )
    list_filter = ("framework", "candidate_class", "is_active")
    search_fields = ("framework__name", "stage__name", "local_name")
    autocomplete_fields = ("framework", "stage")
    actions = None

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.framework.is_system_template:
            return ("framework", "stage")
        return ()

    def has_delete_permission(self, request, obj=None):
        if obj and obj.framework.is_system_template:
            return False
        return super().has_delete_permission(request, obj)


class CampusEducationStageInline(admin.TabularInline):
    model = CampusEducationStage
    extra = 0
    autocomplete_fields = (
        "campus",
        "stage",
        "framework_stage",
        "grading_scale",
    )


class LevelStageMappingInline(admin.TabularInline):
    model = LevelStageMapping
    extra = 0
    autocomplete_fields = ("stage",)


@admin.register(InstitutionEducationProfile)
class InstitutionEducationProfileAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "institution_type",
        "country_code",
        "locale",
        "primary_framework",
        "is_active",
    )
    list_filter = ("institution_type", "country_code", "is_active")
    search_fields = ("organization__name", "primary_framework__name")
    autocomplete_fields = ("organization", "primary_framework")
    inlines = (CampusEducationStageInline, LevelStageMappingInline)


@admin.register(CampusEducationStage)
class CampusEducationStageAdmin(admin.ModelAdmin):
    list_display = (
        "campus",
        "stage",
        "local_name",
        "academic_period_type",
        "grading_scale",
        "default_assessment_mode",
        "report_mode",
        "candidate_class",
        "is_active",
    )
    list_filter = (
        "stage",
        "academic_period_type",
        "default_assessment_mode",
        "report_mode",
        "candidate_class",
        "supports_promotion_decisions",
        "is_active",
    )
    search_fields = (
        "campus__name",
        "stage__name",
        "local_name",
        "grading_scale__name",
        "grading_scale_name",
        "report_layout_key",
    )
    autocomplete_fields = (
        "profile",
        "campus",
        "stage",
        "framework_stage",
        "grading_scale",
    )


@admin.register(LevelStageMapping)
class LevelStageMappingAdmin(admin.ModelAdmin):
    list_display = (
        "legacy_level_name",
        "stage",
        "profile",
        "updated_at",
    )
    list_filter = ("stage",)
    search_fields = (
        "legacy_level_name",
        "local_name",
        "profile__organization__name",
    )
    autocomplete_fields = ("profile", "stage")
