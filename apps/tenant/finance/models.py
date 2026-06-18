from decimal import Decimal
import hashlib
import secrets

from django.db import models
from django.utils import timezone


class FeeItem(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.code else self.name


class Invoice(models.Model):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    STATUS_CHOICES = ((ACTIVE, "Active"), (CLOSED, "Closed"))
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.SET_NULL, null=True, blank=True)
    academic_term = models.ForeignKey("academics.AcademicTerm", on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField(max_length=64, blank=True)
    due_date = models.DateField(null=True, blank=True)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"), help_text="Arrears or balance brought forward from a prior period (added to line totals).")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Invoice #{self.id}"

    def subtotal_lines(self) -> Decimal:
        total = Decimal("0")
        for line in self.lines.all():
            total += line.line_total()
        return total

    def adjustment_total(self) -> Decimal:
        total = Decimal("0")
        if hasattr(self, "adjustments"):
            for adjustment in self.adjustments.all():
                total += adjustment.signed_amount()
        return total

    def total_amount(self) -> Decimal:
        ob = self.opening_balance if self.opening_balance is not None else Decimal("0")
        return ob + self.subtotal_lines() + self.adjustment_total()

    def total_paid(self) -> Decimal:
        total = Decimal("0")
        for p in self.payments.all():
            total += p.amount
        return total

    def balance(self) -> Decimal:
        return self.total_amount() - self.total_paid()


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    fee_item = models.ForeignKey(FeeItem, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return self.description

    def line_total(self) -> Decimal:
        return (self.quantity or Decimal("0")) * (self.unit_amount or Decimal("0"))

    def save(self, *args, **kwargs):
        was_new = self._state.adding
        super().save(*args, **kwargs)
        if was_new:
            try:
                from .accounting_posting import post_invoice_to_ledger
                post_invoice_to_ledger(self.invoice)
            except Exception:
                pass


class Payment(models.Model):
    CASH = "CASH"
    BANK = "BANK"
    MOBILE = "MOBILE"
    CARD = "CARD"
    METHOD_CHOICES = ((CASH, "Cash"), (BANK, "Bank"), (MOBILE, "Mobile money"), (CARD, "Card"))
    MTN_MOMO = "MTN_MOMO"
    AIRTEL_MONEY = "AIRTEL_MONEY"
    MOBILE_OTHER = "OTHER"
    MOBILE_NETWORK_CHOICES = ((MTN_MOMO, "MTN MoMo"), (AIRTEL_MONEY, "Airtel Money"), (MOBILE_OTHER, "Other mobile wallet"))
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default=CASH)
    mobile_network = models.CharField(max_length=16, choices=MOBILE_NETWORK_CHOICES, blank=True, help_text="When paying by mobile money, which network was used (for reconciliation).")
    reference = models.CharField(max_length=128, blank=True)
    received_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.invoice} payment {self.amount}"

    def save(self, *args, **kwargs):
        was_new = self._state.adding
        if self.method != self.MOBILE:
            self.mobile_network = ""
        super().save(*args, **kwargs)
        if was_new:
            try:
                from .accounting_posting import post_payment_to_ledger
                post_payment_to_ledger(self)
            except Exception:
                pass


class MobilePaymentRequest(models.Model):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = ((PENDING, "Pending"), (PROCESSING, "Processing"), (SUCCESSFUL, "Successful"), (FAILED, "Failed"), (CANCELLED, "Cancelled"))
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="mobile_payment_requests")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone_number = models.CharField(max_length=32)
    network = models.CharField(max_length=16, choices=Payment.MOBILE_NETWORK_CHOICES, default=Payment.MTN_MOMO)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    provider_reference = models.CharField(max_length=128, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    created_payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_requests")
    requested_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["invoice", "status"]), models.Index(fields=["provider_reference"])]

    def __str__(self):
        return f"Mobile payment request {self.id} - {self.amount}"


class OutboundMessageLog(models.Model):
    FEE_REMINDER = "FEE_REMINDER"
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT"
    ABSENCE_ALERT = "ABSENCE_ALERT"
    URGENT_ANNOUNCEMENT = "URGENT_ANNOUNCEMENT"
    MESSAGE_TYPE_CHOICES = ((FEE_REMINDER, "Fee reminder"), (PAYMENT_RECEIPT, "Payment receipt"), (ABSENCE_ALERT, "Absence alert"), (URGENT_ANNOUNCEMENT, "Urgent announcement"))
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    CHANNEL_CHOICES = ((SMS, "SMS"), (WHATSAPP, "WhatsApp"))
    SENT = "SENT"
    FAILED = "FAILED"
    DRY_RUN = "DRY_RUN"
    NO_PHONE = "NO_PHONE"
    STATUS_CHOICES = ((SENT, "Sent"), (FAILED, "Failed"), (DRY_RUN, "Dry run"), (NO_PHONE, "No phone"))
    message_type = models.CharField(max_length=32, choices=MESSAGE_TYPE_CHOICES)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default=SMS)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="message_logs")
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="message_logs")
    phone_raw = models.CharField(max_length=64, blank=True)
    phone_normalized = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    provider_message_id = models.CharField(max_length=128, blank=True)
    provider_delivery_status = models.CharField(max_length=32, blank=True)
    provider_delivery_updated_at = models.DateTimeField(null=True, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["message_type", "channel", "status"]), models.Index(fields=["created_at"])]

    def __str__(self):
        phone = self.phone_normalized or self.phone_raw or "?"
        return f"{self.message_type} {self.channel} {self.status} -> {phone}"


class IntegrationApiKey(models.Model):
    name = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256((raw_key or "").encode("utf-8")).hexdigest()

    @classmethod
    def create_with_plaintext(cls, name: str):
        raw_key = secrets.token_urlsafe(32)
        obj = cls.objects.create(name=name.strip() or "Integration Key", key_prefix=raw_key[:10], key_hash=cls.hash_key(raw_key))
        return obj, raw_key

    @classmethod
    def resolve_active_key(cls, raw_key: str):
        if not raw_key:
            return None
        hashed = cls.hash_key(raw_key)
        key_obj = cls.objects.filter(key_hash=hashed, is_active=True).first()
        if key_obj:
            key_obj.last_used_at = timezone.now()
            key_obj.save(update_fields=["last_used_at"])
        return key_obj


class WebhookEndpoint(models.Model):
    EVENT_MESSAGE_LOG_CREATED = "message_log.created"
    EVENT_CHOICES = ((EVENT_MESSAGE_LOG_CREATED, "Message log created"),)
    name = models.CharField(max_length=120)
    target_url = models.URLField(max_length=400)
    secret = models.CharField(max_length=128, blank=True)
    event_type = models.CharField(max_length=64, choices=EVENT_CHOICES, default=EVENT_MESSAGE_LOG_CREATED)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} -> {self.target_url}"


class WebhookDelivery(models.Model):
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries")
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["event_type", "success", "created_at"])]

    def __str__(self):
        return f"{self.event_type} -> {self.endpoint_id} ({'ok' if self.success else 'fail'})"


class WebhookRetryQueueItem(models.Model):
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="retry_items")
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    last_error_message = models.TextField(blank=True)
    last_status_code = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("next_attempt_at", "id")
        indexes = [models.Index(fields=["is_active", "next_attempt_at"]), models.Index(fields=["event_type", "is_active"])]

    def __str__(self):
        return f"Retry {self.event_type} -> endpoint {self.endpoint_id} (attempt {self.attempt_count})"


class InboundWebhookEvent(models.Model):
    provider = models.CharField(max_length=64, default="WHATSAPP")
    event_type = models.CharField(max_length=64, blank=True)
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField(default=dict, blank=True)
    matched_message_logs = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["provider", "signature_valid", "created_at"])]

    def __str__(self):
        return f"{self.provider} {self.event_type or '-'} ({'ok' if self.signature_valid else 'bad-signature'})"


class CommunicationTemplate(models.Model):
    ANY = "ANY"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    CHANNEL_HINT_CHOICES = ((ANY, "Any channel"), (SMS, "SMS"), (WHATSAPP, "WhatsApp"))
    sort_order = models.PositiveSmallIntegerField(default=1)
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    message_type = models.CharField(max_length=32, choices=OutboundMessageLog.MESSAGE_TYPE_CHOICES)
    channel_hint = models.CharField(max_length=16, choices=CHANNEL_HINT_CHOICES, default=ANY, help_text="Hint for staff; sending code may still use another channel based on settings.")
    body = models.TextField(help_text="Plain text. Use placeholders like {{student_name}} — see product docs for the full list.")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"


from .accounting_models import *
