from django.contrib import admin

from .models import Conversation, Message, Announcement


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'content', 'sent_at')
    readonly_fields = ('sent_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'participant_count', 'campus', 'created_by', 'created_at', 'is_archived')
    list_filter = ('is_archived', 'campus', 'created_at')
    search_fields = ('subject',)
    filter_horizontal = ('participants',)
    inlines = [MessageInline]
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'subject', 'participants')
        }),
        ('Context', {
            'fields': ('campus', 'created_by')
        }),
        ('Status', {
            'fields': ('is_archived',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'content_preview', 'sent_at', 'is_deleted')
    list_filter = ('is_deleted', 'sent_at')
    search_fields = ('content', 'sender__username')
    filter_horizontal = ('read_by',)
    readonly_fields = ('sent_at', 'edited_at')
    
    def content_preview(self, obj):
        return obj.content[:50]
    content_preview.short_description = 'Content'


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'scope', 'audience', 'campus', 'is_active', 'is_urgent', 'created_at')
    list_filter = ('is_active', 'is_urgent', 'scope', 'audience', 'campus', 'created_at')
    search_fields = ('title', 'content')
    filter_horizontal = ('read_by',)
    readonly_fields = ('uuid', 'created_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'title', 'content')
        }),
        ('Targeting', {
            'fields': ('scope', 'audience', 'campus', 'class_group', 'created_by')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_urgent', 'expires_at')
        }),
        ('Tracking', {
            'fields': ('read_by',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
