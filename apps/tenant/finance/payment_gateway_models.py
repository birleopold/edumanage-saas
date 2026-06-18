from django.db import models


class PaymentGatewayEvent(models.Model):
    MTN_MOMO = "MTN_MOMO"
    AIRTEL_MONEY = "AIRTEL_MONEY"
    BANK = "BANK"
    PROVIDER_CHOICES = ((MTN_MOMO, "MTN MoMo"), (AIRTEL_MONEY, "Airtel Money"), (BANK, "Bank"))

    INITIATED = "INITIATED"
    CALLBACK = "CALLBACK"
    STATUS_CHECK = "STATUS_CHECK"
    EVENT_TYPE_CHOICES = ((INITIATED, "Initiated"), (CALLBACK, "Callback"), (STATUS_CHECK, "Status check"))

    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES, default=CALLBACK)
    payment_request = models.ForeignKey("finance.MobilePaymentRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="gateway_events")
    provider_reference = models.CharField(max_length=160, blank=True, db_index=True)
    provider_status = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["provider", "provider_reference"]), models.Index(fields=["processed", "created_at"])]

    def __str__(self):
        return f"{self.provider} {self.event_type} {self.provider_reference}"


class DuplicatePaymentAlert(models.Model):
    payment = models.ForeignKey("finance.Payment", on_delete=models.CASCADE, related_name="duplicate_alerts")
    duplicate_of = models.ForeignKey("finance.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="possible_duplicates")
    reason = models.CharField(max_length=255)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-created_at",)

    def __str__(self):
        return f"Duplicate alert for payment {self.payment_id}"
