from django.contrib import admin

from .models import (
    AttendanceAdjustment,
    AttendanceDailyRecord,
    AttendanceDevice,
    AttendanceEvent,
    AttendanceIdentity,
    AttendancePolicy,
    AttendanceSyncCursor,
)


@admin.register(AttendanceDevice)
class AttendanceDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "vendor", "campus", "connection_mode", "is_active", "last_seen_at")
    list_filter = ("vendor", "connection_mode", "is_active", "campus")
    search_fields = ("name", "code", "serial_number", "location")
    readonly_fields = ("token_prefix", "token_hash", "last_seen_at", "last_event_at", "created_at", "updated_at")


@admin.register(AttendanceIdentity)
class AttendanceIdentityAdmin(admin.ModelAdmin):
    list_display = ("namespace", "external_person_id", "person_type", "student", "staff", "is_active")
    list_filter = ("person_type", "is_active", "namespace")
    search_fields = ("external_person_id", "card_number", "student__student_id", "staff__staff_id", "student__first_name", "student__last_name", "staff__first_name", "staff__last_name")


@admin.register(AttendancePolicy)
class AttendancePolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "person_type", "campus", "expected_in", "expected_out", "direction_strategy", "is_default", "is_active")
    list_filter = ("person_type", "direction_strategy", "is_default", "is_active", "campus")


@admin.register(AttendanceEvent)
class AttendanceEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "device", "external_person_id", "student", "staff", "direction", "auth_method", "processing_status")
    list_filter = ("processing_status", "direction", "auth_method", "source", "device")
    search_fields = ("external_person_id", "external_event_id", "event_code", "student__student_id", "staff__staff_id")
    readonly_fields = ("event_hash", "raw_payload", "received_at", "processed_at")


@admin.register(AttendanceDailyRecord)
class AttendanceDailyRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "person_type", "student", "staff", "campus", "status", "first_in", "last_out", "minutes_present", "manual_override")
    list_filter = ("date", "person_type", "status", "manual_override", "campus")
    search_fields = ("student__student_id", "staff__staff_id", "student__first_name", "student__last_name", "staff__first_name", "staff__last_name")


@admin.register(AttendanceAdjustment)
class AttendanceAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("record", "changed_by", "created_at")
    readonly_fields = ("record", "before", "after", "reason", "changed_by", "created_at")


@admin.register(AttendanceSyncCursor)
class AttendanceSyncCursorAdmin(admin.ModelAdmin):
    list_display = ("device", "cursor_key", "cursor_value", "last_synced_at", "updated_at")
    search_fields = ("device__code", "cursor_key", "cursor_value")
