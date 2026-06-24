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
