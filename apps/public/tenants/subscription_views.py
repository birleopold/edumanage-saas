from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PlatformAuditEvent, SubscriptionInvoice, SubscriptionPlan, Tenant, TenantSubscription
from .platform_views import _record_platform_event, platform_admin_required
from .subscription_forms import SubscriptionInvoiceForm, SubscriptionPaymentForm, TenantSubscriptionForm
from .subscription_services import create_subscription_for_tenant, create_subscription_invoice, ensure_default_plans, subscription_usage, sync_subscription_to_tenant_status, usage_percent


def _subscription_initial(subscription: TenantSubscription):
    return {
        "plan": subscription.plan_id,
        "status": subscription.status,
        "billing_cycle": subscription.billing_cycle,
        "payment_status": subscription.payment_status,
        "payment_reference": subscription.payment_reference,
        "notes": subscription.notes,
    }


def _subscription_context(subscription: TenantSubscription):
    usage = subscription_usage(subscription)
    plan = subscription.plan
    return {
        "subscription": subscription,
        "usage": usage,
        "usage_cards": [
            {"label": "Students", "used": usage.get("students"), "limit": plan.max_students, "percent": usage_percent(usage.get("students"), plan.max_students)},
            {"label": "Staff", "used": usage.get("staff"), "limit": plan.max_staff, "percent": usage_percent(usage.get("staff"), plan.max_staff)},
            {"label": "Campuses", "used": usage.get("campuses"), "limit": plan.max_campuses, "percent": usage_percent(usage.get("campuses"), plan.max_campuses)},
            {"label": "Storage MB", "used": None, "limit": plan.max_storage_mb, "percent": None},
        ],
        "invoices": subscription.invoices.all()[:20],
    }


def _backfill_missing_subscriptions():
    ensure_default_plans()
    missing = Tenant.objects.filter(subscription__isnull=True)
    created = 0
    for tenant in missing:
        create_subscription_for_tenant(tenant)
        created += 1
    return created


@platform_admin_required
def subscription_dashboard(request):
    created = _backfill_missing_subscriptions()
    if created:
        messages.info(request, f"Created default subscription records for {created} existing tenant(s).")
    subscriptions = TenantSubscription.objects.select_related("tenant", "plan").all()
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "monthly_price")
    context = {
        "plans": plans,
        "subscriptions": subscriptions[:100],
        "trialing_count": subscriptions.filter(status=TenantSubscription.TRIALING).count(),
        "active_count": subscriptions.filter(status=TenantSubscription.ACTIVE).count(),
        "past_due_count": subscriptions.filter(status=TenantSubscription.PAST_DUE).count(),
        "suspended_count": subscriptions.filter(status=TenantSubscription.SUSPENDED).count(),
        "unpaid_count": subscriptions.exclude(payment_status__in=[TenantSubscription.PAYMENT_PAID, TenantSubscription.PAYMENT_WAIVED]).count(),
    }
    return render(request, "platform/subscriptions/dashboard.html", context)


@platform_admin_required
def tenant_subscription_detail(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    subscription = getattr(tenant, "subscription", None)
    if subscription is None:
        subscription = create_subscription_for_tenant(tenant)
        _record_platform_event(
            request,
            PlatformAuditEvent.SUBSCRIPTION_CREATED,
            tenant=tenant,
            object_label=f"{tenant.name} subscription",
            after={"plan": subscription.plan.code, "status": subscription.status, "amount": str(subscription.amount)},
        )
    if request.method == "POST":
        before = {"plan": subscription.plan.code, "status": subscription.status, "billing_cycle": subscription.billing_cycle, "payment_status": subscription.payment_status}
        form = TenantSubscriptionForm(request.POST)
        if form.is_valid():
            plan = form.cleaned_data["plan"]
            billing_cycle = form.cleaned_data["billing_cycle"]
            subscription.plan = plan
            subscription.status = form.cleaned_data["status"]
            subscription.billing_cycle = billing_cycle
            subscription.currency = plan.currency
            subscription.amount = plan.annual_price if billing_cycle == SubscriptionPlan.ANNUAL else plan.monthly_price
            subscription.payment_status = form.cleaned_data["payment_status"]
            subscription.payment_reference = form.cleaned_data.get("payment_reference", "")
            subscription.notes = form.cleaned_data.get("notes", "")
            subscription.save()
            sync_subscription_to_tenant_status(subscription)
            _record_platform_event(
                request,
                PlatformAuditEvent.SUBSCRIPTION_UPDATED,
                tenant=tenant,
                object_label=f"{tenant.name} subscription",
                before=before,
                after={"plan": subscription.plan.code, "status": subscription.status, "billing_cycle": subscription.billing_cycle, "payment_status": subscription.payment_status},
            )
            messages.success(request, "Subscription updated successfully.")
            return redirect("platform_tenant_subscription", tenant_id=tenant.pk)
    else:
        form = TenantSubscriptionForm(initial=_subscription_initial(subscription))
    context = _subscription_context(subscription)
    context.update({"tenant": tenant, "form": form, "invoice_form": SubscriptionInvoiceForm(), "payment_form": SubscriptionPaymentForm()})
    return render(request, "platform/subscriptions/detail.html", context)


@platform_admin_required
@require_POST
def subscription_create_invoice(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    subscription = getattr(tenant, "subscription", None) or create_subscription_for_tenant(tenant)
    form = SubscriptionInvoiceForm(request.POST)
    if form.is_valid():
        invoice = create_subscription_invoice(subscription, due_on=form.cleaned_data.get("due_on"), notes=form.cleaned_data.get("notes", ""))
        _record_platform_event(
            request,
            PlatformAuditEvent.SUBSCRIPTION_UPDATED,
            tenant=tenant,
            object_label=invoice.invoice_number,
            after={"invoice": invoice.invoice_number, "amount": str(invoice.amount), "due_on": str(invoice.due_on or "")},
        )
        messages.success(request, f"Subscription invoice {invoice.invoice_number} created.")
    else:
        messages.error(request, "Invalid invoice details.")
    return redirect("platform_tenant_subscription", tenant_id=tenant.pk)


@platform_admin_required
@require_POST
def subscription_mark_paid(request, invoice_id):
    invoice = get_object_or_404(SubscriptionInvoice.objects.select_related("subscription", "subscription__tenant"), pk=invoice_id)
    form = SubscriptionPaymentForm(request.POST)
    tenant = invoice.subscription.tenant
    if form.is_valid():
        invoice.status = SubscriptionInvoice.PAID
        invoice.paid_on = timezone.localdate()
        invoice.payment_reference = form.cleaned_data["payment_reference"]
        invoice.notes = form.cleaned_data.get("notes", "")
        invoice.save(update_fields=["status", "paid_on", "payment_reference", "notes", "updated_at"])
        subscription = invoice.subscription
        subscription.payment_status = TenantSubscription.PAYMENT_PAID
        subscription.payment_reference = invoice.payment_reference
        if subscription.status in {TenantSubscription.PAST_DUE, TenantSubscription.SUSPENDED, TenantSubscription.TRIALING}:
            subscription.status = TenantSubscription.ACTIVE
        subscription.save(update_fields=["payment_status", "payment_reference", "status", "updated_at"])
        sync_subscription_to_tenant_status(subscription)
        _record_platform_event(
            request,
            PlatformAuditEvent.SUBSCRIPTION_PAYMENT_RECORDED,
            tenant=tenant,
            object_label=invoice.invoice_number,
            after={"invoice": invoice.invoice_number, "payment_reference": invoice.payment_reference, "amount": str(invoice.amount)},
        )
        messages.success(request, f"Payment recorded for {invoice.invoice_number}.")
    else:
        messages.error(request, "Invalid payment details.")
    return redirect("platform_tenant_subscription", tenant_id=tenant.pk)
