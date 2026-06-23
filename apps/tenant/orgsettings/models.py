from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import connection, models
from django.db.models import Q, Sum
from django.utils import timezone


def branding_upload_to(instance, filename: str) -> str:
    schema = getattr(connection, "schema_name", "public") or "public"
    return f"{schema}/branding/{filename}"


class OrganizationProfile(models.Model):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)

    tenant_schema_name = models.CharField(
        max_length=63,
        blank=True,
        help_text="SaaS tenant schema/slug for this school, for example green_valley_school.",
    )
    tenant_domain = models.CharField(
        max_length=253,
        blank=True,
        help_text="School domain used to access this tenant, for example greenvalley.ac.ug.",
    )
    tenant_status = models.CharField(max_length=32, default="active", blank=True)

    logo = models.FileField(upload_to=branding_upload_to, blank=True)

    primary_color = models.CharField(max_length=32, blank=True)
    secondary_color = models.CharField(max_length=32, blank=True)

    default_currency = models.CharField(
        max_length=3,
        default="UGX",
        help_text="ISO 4217 code shown on invoices and fee statements (e.g. UGX, USD).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Campus(models.Model):
    organization = models.ForeignKey(OrganizationProfile, on_delete=models.CASCADE, related_name="campuses")

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=32, blank=True)

    student_number_format = models.CharField(max_length=200, blank=True)
    last_student_sequence = models.PositiveIntegerField(default=0)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)

    logo_override = models.FileField(upload_to=branding_upload_to, blank=True)
    primary_color_override = models.CharField(max_length=32, blank=True)
    secondary_color_override = models.CharField(max_length=32, blank=True)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        unique_together = (
            ("organization", "name"),
        )
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=~models.Q(code=""),
                name="uniq_campus_code_nonblank",
            )
        ]

    def __str__(self) -> str:
        return self.name


class FeatureFlag(models.Model):
    code = models.CharField(max_length=64)
    is_enabled = models.BooleanField(default=True)

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(campus__isnull=True),
                name="uniq_featureflag_global_code",
            ),
            models.UniqueConstraint(
                fields=["campus", "code"],
                condition=models.Q(campus__isnull=False),
                name="uniq_featureflag_campus_code",
            ),
        ]

    def __str__(self) -> str:
        scope = "global" if self.campus_id is None else f"campus:{self.campus_id}"
        return f"{self.code} ({scope})"


class StatusHistory(models.Model):
    """
    Track status changes for any model with a status field.
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
    In-app notification system.
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
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default=ALL)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, null=True, blank=True)
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=NORMAL)
    link = models.CharField(max_length=255, blank=True)
    
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
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
