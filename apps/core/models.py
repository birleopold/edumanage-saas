"""
Core models for reusable functionality across the application.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


class StatusHistory(models.Model):
    """
    Track status changes for any model with a status field.
    Uses GenericForeignKey to work with any model.
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    old_status = models.CharField(max_length=64, blank=True)
    new_status = models.CharField(max_length=64)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='status_changes'
    )
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name_plural = 'Status histories'
    
    def __str__(self):
        return f"{self.content_type} #{self.object_id}: {self.old_status} → {self.new_status}"


class ActionLog(models.Model):
    """
    Track actions performed on any record.
    Generic action tracking for audit trail.
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    action = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_actions'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.action} on {self.content_type} #{self.object_id}"


class Notification(models.Model):
    """
    In-app notification system with audience targeting.
    """
    NORMAL = 'NORMAL'
    URGENT = 'URGENT'
    CRITICAL = 'CRITICAL'
    
    PRIORITY_CHOICES = (
        (NORMAL, 'Normal'),
        (URGENT, 'Urgent'),
        (CRITICAL, 'Critical'),
    )
    
    ALL = 'ALL'
    ADMIN = 'ADMIN'
    CAMPUS_ADMIN = 'CAMPUS_ADMIN'
    TEACHERS = 'TEACHERS'
    STUDENTS = 'STUDENTS'
    PARENTS = 'PARENTS'
    STAFF = 'STAFF'
    
    AUDIENCE_CHOICES = (
        (ALL, 'All Users'),
        (ADMIN, 'Administrators'),
        (CAMPUS_ADMIN, 'Campus Admins'),
        (TEACHERS, 'Teachers'),
        (STUDENTS, 'Students'),
        (PARENTS, 'Parents'),
        (STAFF, 'Staff'),
    )
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True
    )
    audience = models.CharField(
        max_length=16,
        choices=AUDIENCE_CHOICES,
        default=ALL,
        help_text='Target audience for broadcast notifications'
    )
    campus = models.ForeignKey(
        'orgsettings.Campus',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Campus-specific notification'
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=NORMAL)
    link = models.CharField(max_length=255, blank=True, help_text='Optional link to related page')
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['audience', 'campus']),
        ]
    
    def __str__(self):
        return self.title
    
    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def is_expired(self):
        """Check if notification has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class InventoryItem(models.Model):
    """
    Generic inventory item for tracking stock.
    """
    campus = models.ForeignKey(
        'orgsettings.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    sku = models.CharField(max_length=64, blank=True, help_text='Stock Keeping Unit')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=128, blank=True)
    unit = models.CharField(max_length=32, blank=True, help_text='e.g., pcs, kg, liters')
    
    min_stock_level = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Minimum stock level for alerts'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                fields=['sku'],
                condition=~Q(sku=''),
                name='unique_sku_when_not_blank'
            ),
            models.UniqueConstraint(
                fields=['campus', 'name'],
                name='unique_item_per_campus'
            )
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.name}" if self.sku else self.name
    
    def stock_on_hand(self) -> Decimal:
        """Calculate current stock from movements."""
        totals = self.movements.aggregate(
            in_qty=Sum('quantity', filter=Q(movement_type=StockMovement.IN)),
            out_qty=Sum('quantity', filter=Q(movement_type=StockMovement.OUT)),
            adj_qty=Sum('quantity', filter=Q(movement_type=StockMovement.ADJUST)),
        )
        in_qty = totals.get('in_qty') or Decimal('0')
        out_qty = totals.get('out_qty') or Decimal('0')
        adj_qty = totals.get('adj_qty') or Decimal('0')
        return in_qty - out_qty + adj_qty
    
    def is_below_min_stock(self) -> bool:
        """Check if stock is below minimum level."""
        if self.min_stock_level:
            return self.stock_on_hand() < self.min_stock_level
        return False


class StockMovement(models.Model):
    """
    Track stock movements (in, out, adjustments).
    """
    IN = 'IN'
    OUT = 'OUT'
    ADJUST = 'ADJUST'
    
    MOVEMENT_CHOICES = (
        (IN, 'Stock In'),
        (OUT, 'Stock Out'),
        (ADJUST, 'Adjustment'),
    )
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=16, choices=MOVEMENT_CHOICES, default=IN)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=128, blank=True, help_text='PO number, invoice, etc.')
    note = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['item', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.item} {self.movement_type} {self.quantity}"


class AssetAssignment(models.Model):
    """
    Track assignment of assets to users or students.
    """
    ACTIVE = 'ACTIVE'
    RETURNED = 'RETURNED'
    LOST = 'LOST'
    DAMAGED = 'DAMAGED'
    
    STATUS_CHOICES = (
        (ACTIVE, 'Active'),
        (RETURNED, 'Returned'),
        (LOST, 'Lost'),
        (DAMAGED, 'Damaged'),
    )
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='assignments')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_assignments'
    )
    assigned_to_student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_assignments'
    )
    
    assigned_at = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    returned_at = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    note = models.TextField(blank=True)
    
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_assignments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        assignee = self.assigned_to_student or self.assigned_to_user
        return f"{self.item} x{self.quantity} → {assignee}"
    
    def is_overdue(self):
        """Check if assignment is overdue."""
        if self.status == self.ACTIVE and self.due_date:
            from django.utils import timezone
            return timezone.now().date() > self.due_date
        return False
