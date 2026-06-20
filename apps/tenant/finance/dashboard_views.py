from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.tenant.portals.permissions import admin_portal_required

from .models import FeeItem, Invoice, MobilePaymentRequest, OutboundMessageLog, Payment


def _money_total(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field)).get("total") or Decimal("0")


@admin_portal_required
def finance_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    recent_invoices = (
        Invoice.objects.select_related("student", "academic_year", "academic_term")
        .prefetch_related("lines", "payments")
        .order_by("-created_at")[:8]
    )
    recent_payments = (
        Payment.objects.select_related("invoice", "invoice__student")
        .order_by("-created_at")[:8]
    )

    context = {
        "invoice_count": Invoice.objects.count(),
        "active_invoice_count": Invoice.objects.filter(status=Invoice.ACTIVE).count(),
        "fee_item_count": FeeItem.objects.count(),
        "payment_count": Payment.objects.count(),
        "payments_today": _money_total(Payment.objects.filter(created_at__date=today)),
        "payments_this_month": _money_total(Payment.objects.filter(created_at__date__gte=month_start)),
        "mobile_pending_count": MobilePaymentRequest.objects.filter(
            status__in=[MobilePaymentRequest.PENDING, MobilePaymentRequest.PROCESSING]
        ).count(),
        "failed_message_count": OutboundMessageLog.objects.filter(status=OutboundMessageLog.FAILED).count(),
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
    }
    return render(request, "portals/admin/finance/dashboard.html", context)
