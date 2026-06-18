from django.contrib import admin

from .models import BiometricAttendanceEvent, BiometricDevice, IntegrationApiKeyScope, IntegrationEventLog, IntegrationProviderConfig, IntegrationScope, MeetingSessionLink, SSOLoginProvider


@admin.register(IntegrationProviderConfig)
class IntegrationProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_type", "is_active", "last_test_status", "updated_at")
    list_filter = ("provider_type", "is_active")
    search_fields = ("name", "base_url")


@admin.register(IntegrationScope)
class IntegrationScopeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(IntegrationApiKeyScope)
class IntegrationApiKeyScopeAdmin(admin.ModelAdmin):
    list_display = ("api_key", "scope", "created_at")
    list_filter = ("scope",)


@admin.register(IntegrationEventLog)
class IntegrationEventLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "status", "external_reference", "api_key")
    list_filter = ("event_type", "status")
    search_fields = ("external_reference", "error_message")


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "device_code", "campus", "is_active", "last_seen_at")
    list_filter = ("is_active", "campus")
    search_fields = ("name", "device_code")


@admin.register(BiometricAttendanceEvent)
class BiometricAttendanceEventAdmin(admin.ModelAdmin):
    list_display = ("event_time", "device", "student", "external_person_id", "processed")
    list_filter = ("processed", "device")
    search_fields = ("external_person_id", "student__first_name", "student__last_name")


@admin.register(MeetingSessionLink)
class MeetingSessionLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "provider_type", "offering", "created_at")
    list_filter = ("provider_type",)
    search_fields = ("title", "meeting_url")


@admin.register(SSOLoginProvider)
class SSOLoginProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_type", "is_active", "created_at")
    list_filter = ("provider_type", "is_active")
    search_fields = ("name", "client_id")
