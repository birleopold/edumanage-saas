from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .models import FeeItem, Invoice, MobilePaymentRequest, OutboundMessageLog, Payment


def _money_total(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field)).get("total") or Decimal("0")


def _invoice_queryset_for(user):
    qs = Invoice.objects.select_related("student", "student__campus", "academic_year", "academic_term").prefetch_related("lines", "payments")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(student__campus=scoped)
    return qs


def _payment_queryset_for(user):
    qs = Payment.objects.select_related("invoice", "invoice__student", "invoice__student__campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(invoice__student__campus=scoped)
    return qs


def _mobile_payment_request_queryset_for(user):
    qs = MobilePaymentRequest.objects.select_related("invoice", "invoice__student", "invoice__student__campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(invoice__student__campus=scoped)
    return qs


def _message_log_queryset_for(user):
    qs = OutboundMessageLog.objects.select_related("invoice", "invoice__student", "invoice__student__campus")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(invoice__student__campus=scoped)
    return qs


@admin_portal_required
def finance_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    invoices = _invoice_queryset_for(request.user)
    payments = _payment_queryset_for(request.user)
    mobile_requests = _mobile_payment_request_queryset_for(request.user)
    message_logs = _message_log_queryset_for(request.user)

    recent_invoices = invoices.order_by("-created_at")[:8]
    recent_payments = payments.order_by("-created_at")[:8]

    context = {
        "invoice_count": invoices.count(),
        "active_invoice_count": invoices.filter(status=Invoice.ACTIVE).count(),
        "fee_item_count": FeeItem.objects.count(),
        "payment_count": payments.count(),
        "payments_today": _money_total(payments.filter(created_at__date=today)),
        "payments_this_month": _money_total(payments.filter(created_at__date__gte=month_start)),
        "mobile_pending_count": mobile_requests.filter(
            status__in=[MobilePaymentRequest.PENDING, MobilePaymentRequest.PROCESSING]
        ).count(),
        "failed_message_count": message_logs.filter(status=OutboundMessageLog.FAILED).count(),
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
    }
    return render(request, "portals/admin/finance/dashboard.html", context)
