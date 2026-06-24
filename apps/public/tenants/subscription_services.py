from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .models import SubscriptionInvoice, SubscriptionPlan, TenantSubscription
from .onboarding import tenant_data_context


DEFAULT_PLAN_CODES = (SubscriptionPlan.STARTER, SubscriptionPlan.STANDARD, SubscriptionPlan.ENTERPRISE)


def ensure_default_plans():
    """Keep plan records available even if migrations were skipped in preview."""
    defaults = {
        SubscriptionPlan.STARTER: {
            "name": "Starter",
            "description": "Entry package for small schools starting with core records.",
            "monthly_price": Decimal("150000"),
            "annual_price": Decimal("1500000"),
            "trial_days": 14,
            "max_students": 300,
            "max_staff": 40,
            "max_campuses": 1,
            "max_storage_mb": 2048,
            "features": ["academics", "students", "teachers", "parents", "attendance", "announcements", "documents"],
            "sort_order": 1,
        },
        SubscriptionPlan.STANDARD: {
            "name": "Standard",
            "description": "Recommended package for most schools with finance, reports, exams and communication.",
            "monthly_price": Decimal("300000"),
            "annual_price": Decimal("3000000"),
            "trial_days": 14,
            "max_students": 1200,
            "max_staff": 150,
            "max_campuses": 3,
            "max_storage_mb": 10240,
            "features": ["academics", "admissions", "attendance", "assessments", "announcements", "coursework", "students", "teachers", "parents", "finance", "documents", "timetable", "exams", "reports"],
            "sort_order": 2,
        },
        SubscriptionPlan.ENTERPRISE: {
            "name": "Enterprise",
            "description": "Full package for large or multi-campus schools needing all modules and higher limits.",
            "monthly_price": Decimal("650000"),
            "annual_price": Decimal("6500000"),
            "trial_days": 14,
            "max_students": 0,
            "max_staff": 0,
            "max_campuses": 0,
            "max_storage_mb": 0,
            "features": ["academics", "admissions", "attendance", "assessments", "announcements", "coursework", "students", "teachers", "parents", "finance", "library", "transport", "hostels", "inventory", "documents", "timetable", "exams", "reports", "messaging", "hr", "analytics", "audit"],
            "sort_order": 3,
        },
    }
    plans = {}
    for code, values in defaults.items():
        plan, _created = SubscriptionPlan.objects.update_or_create(code=code, defaults=values)
        plans[code] = plan
    return plans


def _plan_amount(plan: SubscriptionPlan, billing_cycle: str) -> Decimal:
    return plan.annual_price if billing_cycle == SubscriptionPlan.ANNUAL else plan.monthly_price


def create_subscription_for_tenant(tenant, package_code="standard", billing_cycle="monthly") -> TenantSubscription:
    plans = ensure_default_plans()
    plan = plans.get(package_code) or plans[SubscriptionPlan.STANDARD]
    billing_cycle = billing_cycle if billing_cycle in {SubscriptionPlan.MONTHLY, SubscriptionPlan.ANNUAL} else plan.default_billing_cycle
    today = timezone.localdate()
    trial_end = today + timedelta(days=plan.trial_days)
    amount = _plan_amount(plan, billing_cycle)
    subscription, _created = TenantSubscription.objects.update_or_create(
        tenant=tenant,
        defaults={
            "plan": plan,
            "status": TenantSubscription.TRIALING if plan.trial_days else TenantSubscription.ACTIVE,
            "billing_cycle": billing_cycle,
            "currency": plan.currency,
            "amount": amount,
            "trial_start": today if plan.trial_days else None,
            "trial_end": trial_end if plan.trial_days else None,
            "current_period_start": today,
            "current_period_end": trial_end if plan.trial_days else today + timedelta(days=365 if billing_cycle == SubscriptionPlan.ANNUAL else 30),
            "next_billing_date": trial_end if plan.trial_days else today + timedelta(days=365 if billing_cycle == SubscriptionPlan.ANNUAL else 30),
            "payment_status": TenantSubscription.PAYMENT_UNPAID,
        },
    )
    return subscription


def sync_subscription_to_tenant_status(subscription: TenantSubscription):
    tenant = subscription.tenant
    if subscription.status == TenantSubscription.SUSPENDED and tenant.status != "suspended":
        tenant.status = "suspended"
        tenant.save(update_fields=["status"])
    elif subscription.status in {TenantSubscription.TRIALING, TenantSubscription.ACTIVE} and tenant.status == "suspended":
        tenant.status = "active"
        tenant.save(update_fields=["status"])


def subscription_usage(subscription: TenantSubscription) -> dict:
    tenant = subscription.tenant
    usage = {"students": None, "staff": None, "campuses": None, "tenant_schema_used": False}
    try:
        with tenant_data_context(tenant) as schema_used:
            from apps.tenant.orgsettings.models import Campus
            from apps.tenant.students.models import StudentProfile
            from apps.tenant.teachers.models import TeacherProfile

            usage.update(
                {
                    "students": StudentProfile.objects.filter(is_active=True).count(),
                    "staff": TeacherProfile.objects.filter(is_active=True).count(),
                    "campuses": Campus.objects.filter(is_active=True).count(),
                    "tenant_schema_used": schema_used,
                }
            )
    except Exception:
        usage["error"] = "Usage counts unavailable in this environment."
    return usage


def usage_percent(used, limit):
    if used is None or not limit:
        return None
    return min(100, round((used / limit) * 100)) if limit else None


def create_subscription_invoice(subscription: TenantSubscription, *, issued_on=None, due_on=None, notes="") -> SubscriptionInvoice:
    issued_on = issued_on or timezone.localdate()
    due_on = due_on or subscription.next_billing_date
    invoice_number = f"SUB-{subscription.tenant_id}-{issued_on.strftime('%Y%m%d')}-{SubscriptionInvoice.objects.filter(subscription=subscription).count() + 1}"
    return SubscriptionInvoice.objects.create(
        subscription=subscription,
        invoice_number=invoice_number,
        amount=subscription.amount,
        currency=subscription.currency,
        status=SubscriptionInvoice.OPEN,
        issued_on=issued_on,
        due_on=due_on,
        notes=notes,
    )
