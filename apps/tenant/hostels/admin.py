from django.contrib import admin

from .models import (
    Bed,
    BedAllocation,
    BoardingLeave,
    BoardingProfile,
    Hostel,
    HostelRollCall,
    HostelRollCallEntry,
    HostelRoom,
    WelfareCase,
    WelfareCaseAction,
)


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(HostelRoom)
class HostelRoomAdmin(admin.ModelAdmin):
    list_display = ("hostel", "name", "code", "capacity", "is_active")
    list_filter = ("hostel", "is_active")
    search_fields = ("name", "code", "hostel__name")


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ("room", "label", "is_active")
    list_filter = ("room__hostel", "is_active")
    search_fields = ("label", "room__name", "room__hostel__name")


@admin.register(BedAllocation)
class BedAllocationAdmin(admin.ModelAdmin):
    list_display = ("student", "bed", "start_date", "end_date", "status")
    list_filter = ("status", "bed__room__hostel")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "bed__label")
    raw_id_fields = ("student", "bed")


@admin.register(BoardingProfile)
class BoardingProfileAdmin(admin.ModelAdmin):
    list_display = ("student", "boarding_status", "primary_guardian_name", "primary_guardian_phone", "is_active")
    list_filter = ("boarding_status", "is_active", "student__campus")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "primary_guardian_name")
    raw_id_fields = ("student",)


@admin.register(BoardingLeave)
class BoardingLeaveAdmin(admin.ModelAdmin):
    list_display = ("student", "leave_type", "expected_departure_at", "expected_return_at", "status")
    list_filter = ("status", "leave_type", "student__campus")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "destination")
    raw_id_fields = ("student", "bed_allocation", "linked_sickbay_visit", "approved_by", "recorded_by")


class HostelRollCallEntryInline(admin.TabularInline):
    model = HostelRollCallEntry
    extra = 0
    raw_id_fields = ("student", "bed_allocation", "boarding_leave")


@admin.register(HostelRollCall)
class HostelRollCallAdmin(admin.ModelAdmin):
    list_display = ("hostel", "roll_call_date", "shift", "status", "recorded_by")
    list_filter = ("hostel", "shift", "status")
    search_fields = ("hostel__name", "notes")
    raw_id_fields = ("recorded_by",)
    inlines = (HostelRollCallEntryInline,)


@admin.register(WelfareCase)
class WelfareCaseAdmin(admin.ModelAdmin):
    list_display = ("student", "title", "category", "severity", "status", "assigned_to", "confidential")
    list_filter = ("category", "severity", "status", "confidential", "campus")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "title", "summary")
    raw_id_fields = (
        "student",
        "campus",
        "assigned_to",
        "opened_by",
        "linked_sickbay_visit",
        "linked_discipline_incident",
        "linked_bed_allocation",
    )


@admin.register(WelfareCaseAction)
class WelfareCaseActionAdmin(admin.ModelAdmin):
    list_display = ("welfare_case", "action_type", "performed_by", "next_follow_up_at", "created_at")
    list_filter = ("action_type",)
    search_fields = ("welfare_case__title", "note")
    raw_id_fields = ("welfare_case", "performed_by")
