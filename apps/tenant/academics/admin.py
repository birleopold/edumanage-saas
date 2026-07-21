from django.contrib import admin

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    ClassGroupPathwayAssignment,
    Course,
    CourseOffering,
    Enrollment,
    Level,
    Program,
    ProgrammePathway,
    ProgrammePathwayLevel,
    SubjectCombination,
    SubjectCombinationCourse,
)


admin.site.register(AcademicYear)
admin.site.register(AcademicTerm)
admin.site.register(Level)
admin.site.register(Program)
admin.site.register(ClassGroup)
admin.site.register(Course)
admin.site.register(CourseOffering)
admin.site.register(Enrollment)


class ProgrammePathwayLevelInline(admin.TabularInline):
    model = ProgrammePathwayLevel
    extra = 0
    raw_id_fields = ("level",)


@admin.register(ProgrammePathway)
class ProgrammePathwayAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "program", "campus", "stage", "priority", "is_default", "is_active")
    list_filter = ("is_active", "is_default", "campus", "stage", "program")
    search_fields = ("code", "name", "description", "program__name", "program__code")
    raw_id_fields = ("program", "campus", "stage")
    inlines = (ProgrammePathwayLevelInline,)


@admin.register(ProgrammePathwayLevel)
class ProgrammePathwayLevelAdmin(admin.ModelAdmin):
    list_display = ("pathway", "level", "sequence", "minimum_terms", "is_entry", "is_exit", "is_active")
    list_filter = ("is_entry", "is_exit", "is_active")
    search_fields = ("pathway__code", "pathway__name", "level__name")
    raw_id_fields = ("pathway", "level")


class SubjectCombinationCourseInline(admin.TabularInline):
    model = SubjectCombinationCourse
    extra = 0
    raw_id_fields = ("course",)


@admin.register(SubjectCombination)
class SubjectCombinationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "pathway", "level", "minimum_subjects", "maximum_subjects", "priority", "is_active")
    list_filter = ("is_active", "is_default", "pathway", "level")
    search_fields = ("code", "name", "description", "pathway__name", "pathway__program__name")
    raw_id_fields = ("pathway", "level")
    inlines = (SubjectCombinationCourseInline,)


@admin.register(SubjectCombinationCourse)
class SubjectCombinationCourseAdmin(admin.ModelAdmin):
    list_display = ("combination", "course", "role", "subject_group", "order", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("combination__code", "combination__name", "course__code", "course__name")
    raw_id_fields = ("combination", "course")


@admin.register(ClassGroupPathwayAssignment)
class ClassGroupPathwayAssignmentAdmin(admin.ModelAdmin):
    list_display = ("class_group", "pathway", "subject_combination", "academic_term", "is_active")
    list_filter = ("is_active", "academic_term", "pathway")
    search_fields = ("class_group__name", "pathway__code", "pathway__name", "subject_combination__code")
    raw_id_fields = ("class_group", "pathway", "subject_combination", "academic_term")
