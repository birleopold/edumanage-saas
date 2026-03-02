from django.contrib import admin

from .models import (
    ActionLog,
    AssetAssignment,
    InventoryItem,
    Notification,
    StatusHistory,
    StockMovement,
)


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'content_type', 'object_id', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('old_status', 'new_status', 'reason')
    readonly_fields = ('content_type', 'object_id', 'old_status', 'new_status', 'changed_by', 'created_at')
    date_hierarchy = 'created_at'


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'content_type', 'object_id', 'performed_by', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('action', 'description')
    readonly_fields = ('content_type', 'object_id', 'performed_by', 'created_at')
    date_hierarchy = 'created_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'recipient', 'audience', 'priority', 'is_read', 'created_at')
    list_filter = ('priority', 'audience', 'is_read', 'created_at')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'sku', 'name', 'category', 'campus', 'stock_display', 'is_active')
    list_filter = ('campus', 'category', 'is_active')
    search_fields = ('sku', 'name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def stock_display(self, obj):
        stock = obj.stock_on_hand()
        if obj.is_below_min_stock():
            return f"{stock} ⚠️"
        return stock
    stock_display.short_description = 'Stock on Hand'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'movement_type', 'quantity', 'reference', 'created_by', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('item__name', 'reference', 'note')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'quantity', 'assignee', 'status', 'assigned_at', 'due_date')
    list_filter = ('status', 'assigned_at')
    search_fields = ('item__name', 'note')
    readonly_fields = ('created_at',)
    date_hierarchy = 'assigned_at'
    
    def assignee(self, obj):
        return obj.assigned_to_student or obj.assigned_to_user
    assignee.short_description = 'Assigned To'
