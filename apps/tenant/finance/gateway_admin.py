from django.contrib import admin

from .models import (
    BankStatementLine,
    DuplicatePaymentAlert,
    MobilePaymentRequest,
    PaymentGatewayEvent,
)


@admin.register(MobilePaymentRequest)
class MobilePaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "amount",
        "phone_number",
        "network",
        "status",
        "provider_reference",
        "created_at",
    )
    list_filter = ("network", "status", "created_at")
    search_fields = (
        "invoice__reference",
        "phone_number",
        "provider_reference",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(PaymentGatewayEvent)
class PaymentGatewayEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "provider",
        "event_type",
        "provider_reference",
        "provider_status",
        "processed",
    )
    list_filter = ("provider", "event_type", "processed", "created_at")
    search_fields = ("provider_reference", "provider_status", "error_message")
    readonly_fields = ("created_at",)


@admin.register(DuplicatePaymentAlert)
class DuplicatePaymentAlertAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "payment",
        "duplicate_of",
        "reason",
        "is_resolved",
    )
    list_filter = ("is_resolved", "created_at")
    search_fields = ("payment__reference", "duplicate_of__reference", "reason")
    readonly_fields = ("created_at",)


@admin.register(BankStatementLine)
class BankStatementLineAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "cash_account",
        "description",
        "amount",
        "reference",
        "matched_payment",
        "is_reconciled",
    )
    list_filter = ("cash_account", "is_reconciled", "transaction_date")
    search_fields = ("description", "reference", "matched_payment__reference")
    readonly_fields = ("imported_at",)
