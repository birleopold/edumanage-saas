from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True

    def __str__(self) -> str:
        return self.name


class Domain(DomainMixin):
    type = models.CharField(max_length=16, default="SUBDOMAIN")
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.domain
