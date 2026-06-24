from django.conf import settings
from django.db import connection, models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True

    def save(self, *args, **kwargs):
        """Create tenant schemas only when running the PostgreSQL tenant backend.

        The local development settings use SQLite so the Platform Console can be
        previewed without a full multi-tenant database. In that mode we save the
        tenant row and skip schema creation, while production PostgreSQL tenant
        mode keeps the normal automatic schema creation behavior.
        """
        if connection.vendor != "postgresql":
            original = self.auto_create_schema
            self.auto_create_schema = False
            try:
                return super().save(*args, **kwargs)
            finally:
                self.auto_create_schema = original
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Domain(DomainMixin):
    SUBDOMAIN = "SUBDOMAIN"
    CUSTOM = "CUSTOM"
    TYPE_CHOICES = ((SUBDOMAIN, "Subdomain"), (CUSTOM, "Custom domain"))

    DNS_PENDING = "PENDING"
    DNS_VERIFIED = "VERIFIED"
    DNS_FAILED = "FAILED"
    DNS_STATUS_CHOICES = (
        (DNS_PENDING, "Pending"),
        (DNS_VERIFIED, "Verified"),
        (DNS_FAILED, "Failed"),
    )

    SSL_PENDING = "PENDING"
    SSL_ACTIVE = "ACTIVE"
    SSL_FAILED = "FAILED"
    SSL_EXPIRED = "EXPIRED"
    SSL_STATUS_CHOICES = (
        (SSL_PENDING, "Pending"),
        (SSL_ACTIVE, "Active"),
        (SSL_FAILED, "Failed"),
        (SSL_EXPIRED, "Expired"),
    )

    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=SUBDOMAIN)
    verified_at = models.DateTimeField(null=True, blank=True)
    dns_status = models.CharField(max_length=16, choices=DNS_STATUS_CHOICES, default=DNS_PENDING)
    ssl_status = models.CharField(max_length=16, choices=SSL_STATUS_CHOICES, default=SSL_PENDING)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    dns_notes = models.TextField(blank=True)

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None or self.dns_status == self.DNS_VERIFIED

    @property
    def is_ssl_active(self) -> bool:
        return self.ssl_status == self.SSL_ACTIVE

    def __str__(self) -> str:
        return self.domain


class PlatformAuditEvent(models.Model):
    TENANT_CREATED = "TENANT_CREATED"
    TENANT_STATUS_CHANGED = "TENANT_STATUS_CHANGED"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"
    TENANT_REACTIVATED = "TENANT_REACTIVATED"
    DOMAIN_CREATED = "DOMAIN_CREATED"
    DOMAIN_UPDATED = "DOMAIN_UPDATED"
    DOMAIN_VERIFIED = "DOMAIN_VERIFIED"
    DOMAIN_SSL_UPDATED = "DOMAIN_SSL_UPDATED"
    ACTION_CHOICES = (
        (TENANT_CREATED, "Tenant created"),
        (TENANT_STATUS_CHANGED, "Tenant status changed"),
        (TENANT_SUSPENDED, "Tenant suspended"),
        (TENANT_REACTIVATED, "Tenant reactivated"),
        (DOMAIN_CREATED, "Domain created"),
        (DOMAIN_UPDATED, "Domain updated"),
        (DOMAIN_VERIFIED, "Domain verified"),
        (DOMAIN_SSL_UPDATED, "Domain SSL updated"),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_events",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="platform_audit_events")
    domain = models.ForeignKey(Domain, on_delete=models.SET_NULL, null=True, blank=True, related_name="platform_audit_events")
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    object_label = models.CharField(max_length=255, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.actor or '-'} {self.object_label or self.tenant or '-'}"
