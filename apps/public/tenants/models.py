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
    type = models.CharField(max_length=16, default="SUBDOMAIN")
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.domain
