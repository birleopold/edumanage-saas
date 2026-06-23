import re

from django.contrib import admin, messages

from .models import (
    ActionLog,
    Campus,
    FeatureFlag,
    Notification,
    OrganizationProfile,
    StatusHistory,
)


_SCHEMA_RE = re.compile(r"[^a-z0-9_]+")


def _schema_from_name(name: str) -> str:
    base = (name or "school").strip().lower().replace(" ", "_")
    base = _SCHEMA_RE.sub("", base).strip("_") or "school"
    if not base[0].isalpha():
        base = f"school_{base}"
    return base[:63]


def _sync_platform_tenant_from_organization(org: OrganizationProfile):
    try:
        from apps.public.tenants.forms import normalize_domain
        from apps.public.tenants.models import Domain, Tenant
    except Exception:
        return None

    schema_name = org.tenant_schema_name or _schema_from_name(org.name)
    status = org.tenant_status or "active"
    tenant, _ = Tenant.objects.update_or_create(
        schema_name=schema_name,
        defaults={"name": org.name, "status": status},
    )

    update_fields = []
    if not org.tenant_schema_name:
        org.tenant_schema_name = schema_name
        update_fields.append("tenant_schema_name")
    if not org.tenant_status:
        org.tenant_status = status
        update_fields.append("tenant_status")

    domain_name = normalize_domain(org.tenant_domain)
    if domain_name:
        domain, _ = Domain.objects.update_or_create(
            domain=domain_name,
            defaults={"tenant": tenant, "type": "CUSTOM", "is_primary": True},
        )
        Domain.objects.filter(tenant=tenant).exclude(pk=domain.pk).update(is_primary=False)

    if update_fields:
        org.save(update_fields=update_fields)
    return tenant


@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'legal_name', 'tenant_schema_name', 'tenant_domain', 'tenant_status', 'email', 'phone', 'created_at')
    search_fields = ('name', 'legal_name', 'email', 'tenant_schema_name', 'tenant_domain')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('School / Organisation', {
            'fields': ('name', 'legal_name', 'email', 'phone', 'address', 'logo')
        }),
        ('SaaS Tenant & Domain', {
            'fields': ('tenant_schema_name', 'tenant_domain', 'tenant_status'),
            'description': 'These fields create or update the matching SaaS tenant and domain record used for multi-tenant routing.'
        }),
        ('Branding', {
            'fields': ('primary_color', 'secondary_color', 'default_currency')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        tenant = _sync_platform_tenant_from_organization(obj)
        if tenant:
            messages.success(request, f"Linked organisation to SaaS tenant: {tenant.name} ({tenant.schema_name}).")


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
