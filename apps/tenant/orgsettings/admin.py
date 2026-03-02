from django.contrib import admin

from .models import (
    ActionLog,
    Campus,
    FeatureFlag,
    Notification,
    OrganizationProfile,
    StatusHistory,
)


@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'legal_name', 'email', 'phone', 'created_at')
    search_fields = ('name', 'legal_name', 'email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'is_active', 'is_default', 'created_at')
    list_filter = ('is_active', 'is_default', 'organization')
    search_fields = ('name', 'code', 'email')
    readonly_fields = ('created_at',)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_enabled', 'campus', 'updated_at')
    list_filter = ('is_enabled', 'campus')
    search_fields = ('code',)
    readonly_fields = ('updated_at',)


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'content_type', 'object_id', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('old_status', 'new_status', 'reason')
    readonly_fields = ('content_type', 'object_id', 'old_status', 'new_status', 'changed_by', 'created_at', 'metadata')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'content_type', 'object_id', 'performed_by', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('action', 'description')
    readonly_fields = ('content_type', 'object_id', 'action', 'description', 'performed_by', 'created_at', 'metadata')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'recipient', 'audience', 'campus', 'priority', 'is_read', 'created_at')
    list_filter = ('priority', 'audience', 'is_read', 'campus', 'created_at')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'message', 'link', 'priority')
        }),
        ('Targeting', {
            'fields': ('recipient', 'audience', 'campus')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
