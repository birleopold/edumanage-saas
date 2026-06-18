from django.shortcuts import render

from apps.tenant.portals.permissions import admin_portal_required

from .models import BankStatementLine, DuplicatePaymentAlert, MobilePaymentRequest, PaymentGatewayEvent


@admin_portal_required
def payment_reconciliation_dashboard(request):
    summary = {
        "pending_requests": MobilePaymentRequest.objects.filter(status=MobilePaymentRequest.PROCESSING).count(),
        "failed_requests": MobilePaymentRequest.objects.filter(status=MobilePaymentRequest.FAILED).count(),
        "successful_requests": MobilePaymentRequest.objects.filter(status=MobilePaymentRequest.SUCCESSFUL).count(),
        "unprocessed_events": PaymentGatewayEvent.objects.filter(processed=False).count(),
        "duplicate_alerts": DuplicatePaymentAlert.objects.filter(is_resolved=False).count(),
        "unmatched_statement_lines": BankStatementLine.objects.filter(is_reconciled=False).count(),
    }
    return render(request, "portals/admin/finance/payment_reconciliation.html", {
        "summary": summary,
        "recent_requests": MobilePaymentRequest.objects.select_related("invoice", "invoice__student").order_by("-created_at")[:30],
        "recent_events": PaymentGatewayEvent.objects.order_by("-created_at")[:30],
        "duplicate_alerts": DuplicatePaymentAlert.objects.select_related("payment", "duplicate_of").filter(is_resolved=False)[:30],
        "statement_lines": BankStatementLine.objects.select_related("cash_account", "matched_payment").order_by("-transaction_date")[:30],
    })
