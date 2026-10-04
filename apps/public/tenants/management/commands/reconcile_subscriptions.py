from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.public.tenants.models import SubscriptionInvoice, TenantSubscription
from apps.public.tenants.subscription_services import sync_subscription_to_tenant_status


class Command(BaseCommand):
    help = "Reconcile trial expiry, overdue subscription invoices and billing state."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        lock_key = "edumanage:platform:subscription-aging"
        if not cache.add(lock_key, "1", timeout=900):
            self.stdout.write(self.style.WARNING("Subscription aging is already running."))
            return
        try:
            today = timezone.localdate()
            overdue = SubscriptionInvoice.objects.filter(status=SubscriptionInvoice.OPEN, due_on__lt=today).exclude(subscription__tenant__schema_name="public")
            expired_trials = TenantSubscription.objects.filter(status=TenantSubscription.TRIALING, trial_end__lt=today).exclude(tenant__schema_name="public")
            due_subscriptions = TenantSubscription.objects.filter(status=TenantSubscription.ACTIVE, next_billing_date__lt=today).exclude(tenant__schema_name="public").exclude(payment_status__in=[TenantSubscription.PAYMENT_PAID, TenantSubscription.PAYMENT_WAIVED])
            self.stdout.write(f"overdue_invoices={overdue.count()} expired_trials={expired_trials.count()} past_due={due_subscriptions.count()}")
            if options["dry_run"]:
                return
            with transaction.atomic():
                overdue.update(status=SubscriptionInvoice.OVERDUE)
                expired_trials.update(status=TenantSubscription.EXPIRED)
                due_subscriptions.update(status=TenantSubscription.PAST_DUE)
            for subscription in TenantSubscription.objects.filter(status__in=[TenantSubscription.EXPIRED, TenantSubscription.SUSPENDED]).exclude(tenant__schema_name="public"):
                sync_subscription_to_tenant_status(subscription)
        finally:
            cache.delete(lock_key)
