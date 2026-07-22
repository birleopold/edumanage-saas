from django.contrib import admin

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    ClassGroupPathwayAssignment,
    Course,
    CourseOffering,
    Enrollment,
    GradeRange,
    GradingScale,
    Level,
    Program,
    ProgrammePathway,
    ProgrammePathwayLevel,
    SubjectCombination,
    SubjectCombinationCourse,
)
from .pathway_extensions import SubjectCombinationPolicy, SubjectRoleProfile


admin.site.register(AcademicYear)
admin.site.register(AcademicTerm)
admin.site.register(Level)
admin.site.register(Program)
admin.site.register(ClassGroup)
admin.site.register(Course)
admin.site.register(CourseOffering)
admin.site.register(Enrollment)


@admin.register(GradingScale)
class GradingScaleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "is_active", "created_at")
    list_filter = ("is_default", "is_active")
    search_fields = ("name", "description")
    ordering = ("-is_default", "name")


@admin.register(GradeRange)
class GradeRangeAdmin(admin.ModelAdmin):
    list_display = (
        "scale",
        "grade",
        "min_score",
        "max_score",
        "grade_point",
        "order",
    )
    list_filter = ("scale",)
    search_fields = ("scale__name", "grade", "remark")
    autocomplete_fields = ("scale",)
    ordering = ("scale", "order", "-min_score")


class ProgrammePathwayLevelInline(admin.TabularInline):
    model = ProgrammePathwayLevel
    extra = 0
    raw_id_fields = ("level",)


@admin.register(ProgrammePathway)
class ProgrammePathwayAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "program",
        "campus",
        "stage",
        "priority",
        "is_default",
        "is_active",
    )
    list_filter = ("is_active", "is_default", "campus", "stage", "program")
    search_fields = ("code", "name", "description", "program__name", "program__code")
    raw_id_fields = ("program", "campus", "stage")
    inlines = (ProgrammePathwayLevelInline,)


@admin.register(ProgrammePathwayLevel)
class ProgrammePathwayLevelAdmin(admin.ModelAdmin):
    list_display = (
        "pathway",
        "level",
        "sequence",
        "minimum_terms",
        "is_entry",
        "is_exit",
        "is_active",
    )
    list_filter = ("is_entry", "is_exit", "is_active")
    search_fields = ("pathway__code", "pathway__name", "level__name")
    raw_id_fields = ("pathway", "level")


class SubjectRoleProfileInline(admin.StackedInline):
    model = SubjectRoleProfile
    extra = 0
    max_num = 1
    can_delete = False


class SubjectCombinationCourseInline(admin.TabularInline):
    model = SubjectCombinationCourse
    extra = 0
    raw_id_fields = ("course",)


class SubjectCombinationPolicyInline(admin.StackedInline):
    model = SubjectCombinationPolicy
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(SubjectCombination)
class SubjectCombinationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "pathway",
        "level",
        "minimum_subjects",
        "maximum_subjects",
        "priority",
        "is_active",
    )
    list_filter = ("is_active", "is_default", "pathway", "level")
    search_fields = (
        "code",
        "name",
        "description",
        "pathway__name",
        "pathway__program__name",
    )
    raw_id_fields = ("pathway", "level")
    inlines = (SubjectCombinationPolicyInline, SubjectCombinationCourseInline)


@admin.register(SubjectCombinationCourse)
class SubjectCombinationCourseAdmin(admin.ModelAdmin):
    list_display = (
        "combination",
        "course",
        "role",
        "academic_role",
        "subject_group",
        "order",
        "is_active",
    )
    list_filter = (
        "role",
        "academic_role_profile__academic_role",
        "is_active",
    )
    search_fields = (
        "combination__code",
        "combination__name",
        "course__code",
        "course__name",
    )
    raw_id_fields = ("combination", "course")
    inlines = (SubjectRoleProfileInline,)

    @admin.display(description="Academic role")
    def academic_role(self, obj):
        try:
            return obj.academic_role_profile.get_academic_role_display()
        except SubjectRoleProfile.DoesNotExist:
            return "Not configured"


@admin.register(SubjectCombinationPolicy)
class SubjectCombinationPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "combination",
        "maximum_students",
        "minimum_principal_subjects",
        "maximum_principal_subjects",
        "minimum_subsidiary_subjects",
        "maximum_subsidiary_subjects",
        "require_general_paper",
    )
    list_filter = ("require_general_paper",)
    search_fields = (
        "combination__code",
        "combination__name",
        "combination__pathway__name",
    )
    raw_id_fields = ("combination",)


@admin.register(SubjectRoleProfile)
class SubjectRoleProfileAdmin(admin.ModelAdmin):
    list_display = (
        "membership",
        "academic_role",
        "contributes_principal_points",
        "contributes_subsidiary_points",
        "required_for_completion",
    )
    list_filter = (
        "academic_role",
        "contributes_principal_points",
        "contributes_subsidiary_points",
        "required_for_completion",
    )
    search_fields = (
        "membership__combination__code",
        "membership__combination__name",
        "membership__course__code",
        "membership__course__name",
    )
    raw_id_fields = ("membership",)


@admin.register(ClassGroupPathwayAssignment)
class ClassGroupPathwayAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "class_group",
        "pathway",
        "subject_combination",
        "academic_term",
        "is_active",
    )
    list_filter = ("is_active", "academic_term", "pathway")
    search_fields = (
        "class_group__name",
        "pathway__code",
        "pathway__name",
        "subject_combination__code",
    )
    raw_id_fields = (
        "class_group",
        "pathway",
        "subject_combination",
        "academic_term",
    )
