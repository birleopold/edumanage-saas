from django.contrib import admin

from .models import (
    CommunicationTemplate,
    FeeItem,
    InboundWebhookEvent,
    IntegrationApiKey,
    Invoice,
    InvoiceLine,
    OutboundMessageLog,
    Payment,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookRetryQueueItem,
)


@admin.register(CommunicationTemplate)
class CommunicationTemplateAdmin(admin.ModelAdmin):
    list_display = ("sort_order", "name", "code", "message_type", "channel_hint", "is_active", "updated_at")
    list_filter = ("message_type", "channel_hint", "is_active")
    search_fields = ("name", "code", "body")
    ordering = ("sort_order", "name")


@admin.register(FeeItem)
class FeeItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "amount", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "academic_year", "academic_term", "status", "due_date", "created_at")
    search_fields = ("reference", "student__first_name", "student__last_name", "student__student_id")
    list_filter = ("status", "academic_year", "academic_term")
    inlines = [InvoiceLineInline, PaymentInline]


@admin.register(OutboundMessageLog)
class OutboundMessageLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "message_type",
        "channel",
        "status",
        "phone_normalized",
        "invoice",
        "payment",
        "provider_message_id",
        "provider_delivery_status",
        "provider_delivery_updated_at",
    )
    search_fields = ("phone_raw", "phone_normalized", "provider_message_id", "error_message")
    list_filter = ("message_type", "channel", "status", "created_at")
    readonly_fields = ("created_at",)


@admin.register(IntegrationApiKey)
class IntegrationApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key_prefix", "is_active", "last_used_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key_prefix")
    readonly_fields = ("key_hash", "last_used_at", "created_at")


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "event_type", "target_url", "is_active", "created_at")
    list_filter = ("event_type", "is_active")
    search_fields = ("name", "target_url")


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "endpoint", "event_type", "status_code", "success")
    list_filter = ("event_type", "success")
    search_fields = ("endpoint__name", "error_message", "response_body")
    readonly_fields = ("created_at",)


@admin.register(WebhookRetryQueueItem)
class WebhookRetryQueueItemAdmin(admin.ModelAdmin):
    list_display = ("id", "endpoint", "event_type", "attempt_count", "max_attempts", "next_attempt_at", "is_active")
    list_filter = ("event_type", "is_active")
    search_fields = ("endpoint__name", "event_type", "last_error_message")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InboundWebhookEvent)
class InboundWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "event_type", "signature_valid", "matched_message_logs")
    list_filter = ("provider", "signature_valid")
    search_fields = ("event_type", "error_message")
    readonly_fields = ("created_at",)
