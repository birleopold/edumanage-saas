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


class SubscriptionPlan(models.Model):
    STARTER = "starter"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"
    PLAN_CHOICES = (
        (STARTER, "Starter"),
        (STANDARD, "Standard"),
        (ENTERPRISE, "Enterprise"),
        (CUSTOM, "Custom"),
    )

    MONTHLY = "monthly"
    ANNUAL = "annual"
    BILLING_CHOICES = ((MONTHLY, "Monthly"), (ANNUAL, "Annual"))

    code = models.SlugField(max_length=50, unique=True, choices=PLAN_CHOICES)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=8, default="UGX")
    monthly_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    default_billing_cycle = models.CharField(max_length=16, choices=BILLING_CHOICES, default=MONTHLY)
    trial_days = models.PositiveIntegerField(default=14)
    max_students = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    max_staff = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    max_campuses = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    max_storage_mb = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "monthly_price", "name")

    def __str__(self) -> str:
        return self.name


class TenantSubscription(models.Model):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = (
        (TRIALING, "Trialing"),
        (ACTIVE, "Active"),
        (PAST_DUE, "Past due"),
        (SUSPENDED, "Suspended"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    )

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID = "paid"
    PAYMENT_WAIVED = "waived"
    PAYMENT_CHOICES = (
        (PAYMENT_UNPAID, "Unpaid"),
        (PAYMENT_PARTIAL, "Partial"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_WAIVED, "Waived"),
    )

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=TRIALING)
    billing_cycle = models.CharField(max_length=16, choices=SubscriptionPlan.BILLING_CHOICES, default=SubscriptionPlan.MONTHLY)
    currency = models.CharField(max_length=8, default="UGX")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    trial_start = models.DateField(null=True, blank=True)
    trial_end = models.DateField(null=True, blank=True)
    current_period_start = models.DateField(null=True, blank=True)
    current_period_end = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    payment_status = models.CharField(max_length=16, choices=PAYMENT_CHOICES, default=PAYMENT_UNPAID)
    payment_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["status", "next_billing_date"]),
            models.Index(fields=["payment_status", "next_billing_date"]),
        ]

    @property
    def is_usable(self) -> bool:
        return self.status in {self.TRIALING, self.ACTIVE}

    def __str__(self) -> str:
        return f"{self.tenant} · {self.plan} · {self.status}"


class SubscriptionInvoice(models.Model):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    OVERDUE = "overdue"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (OPEN, "Open"),
        (PAID, "Paid"),
        (VOID, "Void"),
        (OVERDUE, "Overdue"),
    )

    subscription = models.ForeignKey(TenantSubscription, on_delete=models.CASCADE, related_name="invoices")
    invoice_number = models.CharField(max_length=80, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="UGX")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    issued_on = models.DateField()
    due_on = models.DateField(null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-issued_on", "-id")
        indexes = [models.Index(fields=["status", "due_on"])]

    def __str__(self) -> str:
        return self.invoice_number


class PlatformAuditEvent(models.Model):
    TENANT_CREATED = "TENANT_CREATED"
    TENANT_STATUS_CHANGED = "TENANT_STATUS_CHANGED"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"
    TENANT_REACTIVATED = "TENANT_REACTIVATED"
    DOMAIN_CREATED = "DOMAIN_CREATED"
    DOMAIN_UPDATED = "DOMAIN_UPDATED"
    DOMAIN_VERIFIED = "DOMAIN_VERIFIED"
    DOMAIN_SSL_UPDATED = "DOMAIN_SSL_UPDATED"
    SUBSCRIPTION_CREATED = "SUBSCRIPTION_CREATED"
    SUBSCRIPTION_UPDATED = "SUBSCRIPTION_UPDATED"
    SUBSCRIPTION_PAYMENT_RECORDED = "SUBSCRIPTION_PAYMENT_RECORDED"
    ACTION_CHOICES = (
        (TENANT_CREATED, "Tenant created"),
        (TENANT_STATUS_CHANGED, "Tenant status changed"),
        (TENANT_SUSPENDED, "Tenant suspended"),
        (TENANT_REACTIVATED, "Tenant reactivated"),
        (DOMAIN_CREATED, "Domain created"),
        (DOMAIN_UPDATED, "Domain updated"),
        (DOMAIN_VERIFIED, "Domain verified"),
        (DOMAIN_SSL_UPDATED, "Domain SSL updated"),
        (SUBSCRIPTION_CREATED, "Subscription created"),
        (SUBSCRIPTION_UPDATED, "Subscription updated"),
        (SUBSCRIPTION_PAYMENT_RECORDED, "Subscription payment recorded"),
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