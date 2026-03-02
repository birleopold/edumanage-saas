from django.contrib import admin

from .models import Poll, PollOption, PollVote


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 3
    fields = ('option_text', 'order', 'vote_count')
    readonly_fields = ('vote_count',)


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'campus', 'is_active', 'total_votes', 'created_at')
    list_filter = ('is_active', 'audience', 'campus', 'created_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('specific_students', 'specific_teachers')
    inlines = [PollOptionInline]
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description')
        }),
        ('Targeting', {
            'fields': ('campus', 'audience', 'specific_students', 'specific_teachers', 'created_by')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_anonymous', 'allow_multiple_votes', 'show_results_before_voting')
        }),
        ('Availability', {
            'fields': ('available_from', 'available_until')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_votes(self, obj):
        return obj.get_total_votes()
    total_votes.short_description = 'Total Votes'


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = ('poll', 'option_text', 'vote_count', 'percentage', 'order')
    list_filter = ('poll',)
    search_fields = ('option_text',)
    readonly_fields = ('vote_count', 'created_at')
    
    def percentage(self, obj):
        return f"{obj.get_percentage()}%"
    percentage.short_description = 'Percentage'


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ('poll', 'option', 'user_display', 'voted_at')
    list_filter = ('poll', 'voted_at')
    search_fields = ('user__username', 'option__option_text')
    readonly_fields = ('voted_at',)
    
    def user_display(self, obj):
        return obj.user.username if obj.user else 'Anonymous'
    user_display.short_description = 'User'
