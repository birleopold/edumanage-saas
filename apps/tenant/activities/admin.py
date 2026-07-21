from django.contrib import admin

from .models import Activity, ActivityMember
from .programme_models import (
    ActivityAchievement,
    ActivityAttendance,
    ActivityGroup,
    ActivityParticipation,
    ActivityProgramme,
    ActivitySession,
)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "campus", "head", "is_active")
    list_filter = ("type", "is_active", "campus")
    search_fields = ("name", "description")


@admin.register(ActivityMember)
class ActivityMemberAdmin(admin.ModelAdmin):
    list_display = ("activity", "student", "joined_at", "is_active")
    list_filter = ("activity", "is_active")
    search_fields = ("student__first_name", "student__last_name", "student__student_id")
    raw_id_fields = ("activity", "student")


@admin.register(ActivityProgramme)
class ActivityProgrammeAdmin(admin.ModelAdmin):
    list_display = ("activity", "code", "participation_mode", "capacity", "is_active")
    list_filter = ("participation_mode", "competitive", "is_active")
    search_fields = ("activity__name", "code")
    raw_id_fields = ("activity",)


@admin.register(ActivityGroup)
class ActivityGroupAdmin(admin.ModelAdmin):
    list_display = ("programme", "name", "group_type", "coach", "capacity", "is_active")
    list_filter = ("group_type", "is_active")
    search_fields = ("programme__activity__name", "name")
    raw_id_fields = ("programme", "coach")


@admin.register(ActivityParticipation)
class ActivityParticipationAdmin(admin.ModelAdmin):
    list_display = ("membership", "role", "group", "guardian_consent_status", "medical_clearance_status")
    list_filter = ("role", "guardian_consent_status", "medical_clearance_status")
    search_fields = ("membership__student__first_name", "membership__student__last_name", "membership__activity__name")
    raw_id_fields = ("membership", "group", "updated_by")


class ActivityAttendanceInline(admin.TabularInline):
    model = ActivityAttendance
    extra = 0
    raw_id_fields = ("membership", "marked_by")


@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    list_display = ("title", "activity", "session_type", "starts_at", "status")
    list_filter = ("session_type", "status", "activity")
    search_fields = ("title", "activity__name", "location")
    raw_id_fields = ("activity", "group", "created_by")
    inlines = (ActivityAttendanceInline,)


@admin.register(ActivityAchievement)
class ActivityAchievementAdmin(admin.ModelAdmin):
    list_display = ("membership", "title", "achievement_type", "level", "achieved_on")
    list_filter = ("achievement_type", "level")
    search_fields = ("membership__student__first_name", "membership__student__last_name", "title")
    raw_id_fields = ("membership", "session", "recorded_by")
