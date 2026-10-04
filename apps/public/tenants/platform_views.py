from functools import wraps
import hashlib
import json
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import DomainForm, TenantForm, TenantStatusForm
from .dns_targets import get_dns_targets
from .domain_readiness import inspect_domain
from .models import Domain, PlatformAuditEvent, SubscriptionInvoice, Tenant, TenantSubscription
from .platform_permissions import platform_can, platform_role
from .subscription_services import create_subscription_for_tenant, subscription_usage


PLATFORM_PAGE_SIZE = 25
PLATFORM_CNAME_TARGET = "edumanage.leosoftug.com"
PLATFORM_A_RECORD_TARGET = "YOUR_EDUMANAGE_SERVER_IP"
TENANT_LOGIN_PATH = "/login/"
TENANT_SETUP_GUIDE_PATH = "/admin/school-setup/"


def _login_redirect_url(request):
    query = urlencode({"next": request.get_full_path()})
    return f"{reverse('platform_admin_login')}?{query}"


def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return None


def platform_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and platform_role(request.user):
            if getattr(settings, "PLATFORM_2FA_REQUIRED", True) and not request.session.get("platform_2fa_verified"):
                return redirect("platform_verify_2fa")
            return view_func(request, *args, **kwargs)
        if request.user.is_authenticated:
            messages.error(request, "This account is not assigned an active Platform Console role.")
            return redirect("landing_page")
        return redirect(_login_redirect_url(request))

    return wrapper


def _schema_status(schema_name):
    if connection.vendor != "postgresql":
        return {
            "exists": None,
            "label": "Preview mode",
            "detail": "Schema creation is skipped while using SQLite/local preview settings.",
        }
    with connection.cursor() as cursor:
        cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", [schema_name])
        exists = cursor.fetchone() is not None
    return {
        "exists": exists,
        "label": "Schema ready" if exists else "Schema missing",
        "detail": "Tenant schema exists in PostgreSQL." if exists else "Run tenant migrations or re-check schema creation.",
    }


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _record_platform_event(request, action, *, tenant=None, domain=None, object_label="", before=None, after=None, metadata=None):
    previous = PlatformAuditEvent.objects.order_by("-id").first()
    previous_hash = previous.event_hash if previous else ""
    payload = {"action": action, "actor_id": getattr(getattr(request, "user", None), "id", None), "tenant_id": getattr(tenant, "id", None), "domain_id": getattr(domain, "id", None), "object_label": object_label, "before": before or {}, "after": after or {}, "metadata": metadata or {}, "previous_hash": previous_hash}
    event_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return PlatformAuditEvent.objects.create(
        previous_hash=previous_hash, event_hash=event_hash,
        actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        tenant=tenant,
        domain=domain,
        action=action,
        object_label=object_label,
        before=before or {},
        after=after or {},
        metadata=metadata or {},
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


def _tenant_absolute_url(domain_name: str, path: str = "/") -> str:
    path = path if path.startswith("/") else f"/{path}"
    return f"https://{domain_name}{path}"


def _onboarding_event_metadata(onboarding):
    return {
        "admin_username": onboarding.admin_user.username,
        "login_domain": onboarding.login_domain,
        "login_url": _tenant_absolute_url(onboarding.login_domain, TENANT_LOGIN_PATH),
        "setup_guide_path": TENANT_SETUP_GUIDE_PATH,
        "setup_guide_url": _tenant_absolute_url(onboarding.login_domain, TENANT_SETUP_GUIDE_PATH),
        "organization_id": getattr(onboarding.organization, "id", None),
        "campus_id": getattr(onboarding.campus, "id", None),
        "campus_name": getattr(onboarding.campus, "name", ""),
        "setup_token_created": onboarding.setup_token is not None,
        "tenant_schema_used": onboarding.tenant_schema_used,
        "academic_year": getattr(onboarding.academic_year, "name", ""),
        "academic_term": str(onboarding.academic_term),
        "feature_flags_created": onboarding.feature_flags_created,
        "feature_flags_total": onboarding.feature_flags_total,
    }


def _tenant_onboarding_handoff(tenant, domains, subscription):
    primary_domain = next((domain for domain in domains if domain.is_primary), domains[0] if domains else None)
    created_event = (
        PlatformAuditEvent.objects.filter(tenant=tenant, action=PlatformAuditEvent.TENANT_CREATED)
        .order_by("-created_at")
        .first()
    )
    metadata = created_event.metadata if created_event else {}
    domain_name = metadata.get("login_domain") or getattr(primary_domain, "domain", "")
    login_url = metadata.get("login_url") or (_tenant_absolute_url(domain_name, TENANT_LOGIN_PATH) if domain_name else "")
    setup_guide_url = metadata.get("setup_guide_url") or (_tenant_absolute_url(domain_name, TENANT_SETUP_GUIDE_PATH) if domain_name else "")
    steps = [
        {"title": "Tenant activated", "description": "School status allows users into the tenant portal.", "done": tenant.status == "active", "detail": tenant.status.title()},
        {"title": "Primary login domain assigned", "description": "The school has a primary web address for first login.", "done": primary_domain is not None, "detail": getattr(primary_domain, "domain", "No domain")},
        {"title": "DNS verified", "description": "DNS has been checked before the school is sent live credentials.", "done": bool(primary_domain and primary_domain.is_verified), "detail": primary_domain.get_dns_status_display() if primary_domain else "Pending"},
        {"title": "SSL active", "description": "The login address is ready for secure browser access.", "done": bool(primary_domain and primary_domain.is_ssl_active), "detail": primary_domain.get_ssl_status_display() if primary_domain else "Pending"},
        {"title": "Subscription usable", "description": "Billing state permits the school to operate.", "done": bool(subscription and subscription.is_usable), "detail": subscription.get_status_display() if subscription else "Missing"},
        {"title": "Owner first-login path ready", "description": "Platform staff can hand the owner their username, login URL and setup checklist.", "done": bool(metadata.get("admin_username") and login_url and setup_guide_url), "detail": metadata.get("admin_username") or "Not recorded"},
    ]
    done_count = sum(1 for step in steps if step["done"])
    return {
        "primary_domain": primary_domain,
        "admin_username": metadata.get("admin_username", ""),
        "login_url": login_url,
        "setup_guide_url": setup_guide_url,
        "metadata": metadata,
        "steps": steps,
        "done_count": done_count,
        "total": len(steps),
        "percent": round((done_count / len(steps)) * 100) if steps else 100,
        "ready": done_count == len(steps),
    }


def _domain_dns_instructions(domain):
    targets = get_dns_targets()
    if domain.type == Domain.SUBDOMAIN:
        return {"summary": "Point this EduManage subdomain to the platform host.", "records": [{"type": "CNAME", "host": domain.domain, "value": targets["cname_target"]}], "example": "schoolname.schools.leosoftug.com"}
    return {
        "summary": "At the domain provider, point the school hostname to EduManage. Use A for a root/apex domain and CNAME for a portal or www hostname.",
        "records": [{"type": "A", "host": "@", "value": targets["a_record_target"]}, {"type": "CNAME", "host": "www", "value": targets["cname_target"]}],
        "example": "schoolname.ac.ug", "a_record_ready": targets["a_record_ready"], "a_record_source": targets["a_record_source"],
    }


def _domain_management_rows(domains):
    return [{"domain": domain, "dns": _domain_dns_instructions(domain), "dns_label": domain.get_dns_status_display(), "ssl_label": domain.get_ssl_status_display()} for domain in domains]


def _platform_activity_queryset(request):
    qs = PlatformAuditEvent.objects.select_related("actor", "tenant", "domain")
    action = request.GET.get("action", "")
    tenant_id = request.GET.get("tenant", "")
    q = request.GET.get("q", "").strip()
    if action:
        qs = qs.filter(action=action)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    if q:
        qs = qs.filter(Q(object_label__icontains=q) | Q(tenant__name__icontains=q) | Q(domain__domain__icontains=q) | Q(actor__username__icontains=q))
    return qs


def _activity_summary_cards():
    return [
        {"label": "Tenant actions", "count": PlatformAuditEvent.objects.filter(action__in=[PlatformAuditEvent.TENANT_CREATED, PlatformAuditEvent.TENANT_STATUS_CHANGED, PlatformAuditEvent.TENANT_SUSPENDED, PlatformAuditEvent.TENANT_REACTIVATED]).count()},
        {"label": "Domain actions", "count": PlatformAuditEvent.objects.filter(action__in=[PlatformAuditEvent.DOMAIN_CREATED, PlatformAuditEvent.DOMAIN_UPDATED, PlatformAuditEvent.DOMAIN_VERIFIED, PlatformAuditEvent.DOMAIN_SSL_UPDATED]).count()},
        {"label": "Subscription actions", "count": PlatformAuditEvent.objects.filter(action__in=[PlatformAuditEvent.SUBSCRIPTION_CREATED, PlatformAuditEvent.SUBSCRIPTION_UPDATED, PlatformAuditEvent.SUBSCRIPTION_PAYMENT_RECORDED]).count()},
        {"label": "Suspensions", "count": PlatformAuditEvent.objects.filter(action=PlatformAuditEvent.TENANT_SUSPENDED).count()},
    ]


def _parse_platform_per_page(request, default=PLATFORM_PAGE_SIZE, maximum=100):
    try:
        value = int(request.GET.get("per_page") or default)
    except (TypeError, ValueError):
        value = default
    return max(10, min(value, maximum))


@platform_admin_required
def platform_logout(request):
    logout(request)
    messages.info(request, "You have signed out of the Platform Console.")
    return redirect("platform_admin_login")


@platform_admin_required
def dashboard(request):
    tenants = Tenant.objects.annotate(domain_count=Count("domains", distinct=True)).order_by("-created_at")[:8]
    domains = Domain.objects.select_related("tenant").order_by("-is_primary", "domain")[:10]
    recent_platform_events = PlatformAuditEvent.objects.select_related("actor", "tenant", "domain")[:8]
    verified_domain_count = Domain.objects.filter(Q(verified_at__isnull=False) | Q(dns_status=Domain.DNS_VERIFIED)).distinct().count()
    domain_count = Domain.objects.count()
    schema_missing_count = sum(1 for tenant in Tenant.objects.filter(status="active") if _schema_status(tenant.schema_name).get("exists") is False)
    subscriptions = TenantSubscription.objects.all()
    overdue_invoice_count = SubscriptionInvoice.objects.filter(status=SubscriptionInvoice.OVERDUE).count()
    due_soon = timezone.localdate() + timezone.timedelta(days=7)
    billing_due_soon_count = subscriptions.filter(next_billing_date__isnull=False, next_billing_date__lte=due_soon).exclude(status__in=[TenantSubscription.CANCELLED, TenantSubscription.EXPIRED]).count()
    past_due_subscription_count = subscriptions.filter(status=TenantSubscription.PAST_DUE).count()
    return render(
        request,
        "platform/dashboard.html",
        {
            "tenant_count": Tenant.objects.count(),
            "active_count": Tenant.objects.filter(status="active").count(),
            "pending_count": Tenant.objects.filter(status="pending").count(),
            "suspended_count": Tenant.objects.filter(status="suspended").count(),
            "domain_count": domain_count,
            "verified_domain_count": verified_domain_count,
            "unverified_domain_count": max(0, domain_count - verified_domain_count),
            "ssl_active_domain_count": Domain.objects.filter(ssl_status=Domain.SSL_ACTIVE).count(),
            "schema_missing_count": schema_missing_count,
            "overdue_invoice_count": overdue_invoice_count,
            "billing_due_soon_count": billing_due_soon_count,
            "past_due_subscription_count": past_due_subscription_count,
            "tenants": tenants,
            "domains": domains,
            "recent_platform_events": recent_platform_events,
        },
    )


@platform_admin_required
def platform_activity(request):
    queryset = _platform_activity_queryset(request)
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    selected_action = request.GET.get("action", "")
    selected_tenant = request.GET.get("tenant", "")
    search_query = request.GET.get("q", "")
    return render(
        request,
        "platform/activity.html",
        {
            "page_obj": page_obj,
            "events": page_obj.object_list,
            "actions": PlatformAuditEvent.ACTION_CHOICES,
            "action_choices": PlatformAuditEvent.ACTION_CHOICES,
            "tenants": Tenant.objects.order_by("name"),
            "summary_cards": _activity_summary_cards(),
            "selected_action": selected_action,
            "selected_tenant": selected_tenant,
            "search_query": search_query,
            "active_action": selected_action,
            "active_tenant": selected_tenant,
            "q": search_query,
        },
    )


@platform_admin_required
def tenant_list(request):
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    per_page = _parse_platform_per_page(request)
    tenants = Tenant.objects.annotate(domain_count=Count("domains", distinct=True)).prefetch_related("domains").order_by("-created_at")
    if status:
        tenants = tenants.filter(status=status)
    if q:
        tenants = tenants.filter(Q(name__icontains=q) | Q(schema_name__icontains=q) | Q(domains__domain__icontains=q)).distinct()
    paginator = Paginator(tenants, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "platform/tenant_list.html",
        {"page_obj": page_obj, "tenants": page_obj.object_list, "status": status, "q": q, "per_page": per_page, "statuses": ["active", "pending", "suspended", "archived"]},
    )


@platform_admin_required
def tenant_create(request):
    if not platform_can(request.user, "onboarding"):
        return redirect("platform_access_denied")
    if request.method == "POST":
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            onboarding = getattr(form, "onboarding_result", None)
            primary_domain = tenant.domains.filter(is_primary=True).first()
            _record_platform_event(
                request,
                PlatformAuditEvent.TENANT_CREATED,
                tenant=tenant,
                domain=primary_domain,
                object_label=tenant.name,
                after={"name": tenant.name, "schema_name": tenant.schema_name, "status": tenant.status},
                metadata=_onboarding_event_metadata(onboarding) if onboarding else {},
            )
            messages.success(request, f"Tenant {tenant.name} created successfully.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm()
    return render(request, "platform/tenant_form.html", {"form": form, "mode": "create"})


@platform_admin_required
def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    domains = list(tenant.domains.order_by("-is_primary", "domain"))
    subscription = getattr(tenant, "subscription", None) or create_subscription_for_tenant(tenant)
    schema_status = _schema_status(tenant.schema_name)
    usage = subscription_usage(subscription)
    recent_activity = PlatformAuditEvent.objects.filter(tenant=tenant).select_related("actor", "domain")[:10]
    health = {
        "schema_ready": schema_status.get("exists") is not False,
        "primary_domain_ready": bool(domains and next((d for d in domains if d.is_primary and d.is_verified and d.is_ssl_active), None)),
        "subscription_ready": subscription.is_usable,
        "usage_available": not bool(usage.get("error")),
    }
    health["ready_count"] = sum(1 for value in health.values() if value is True)
    health["total"] = 4
    return render(request, "platform/tenant_detail.html", {"tenant": tenant, "domains": domains, "domain_management": _domain_management_rows(domains), "status_form": TenantStatusForm(initial={"status": tenant.status}), "schema_status": schema_status, "subscription": subscription, "onboarding_handoff": _tenant_onboarding_handoff(tenant, domains, subscription), "platform_usage": usage, "recent_tenant_activity": recent_activity, "operational_health": health})


@platform_admin_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            before = {"name": tenant.name, "schema_name": tenant.schema_name, "status": tenant.status}
            tenant = form.save()
            _record_platform_event(request, PlatformAuditEvent.TENANT_STATUS_CHANGED, tenant=tenant, object_label=tenant.name, before=before, after={"name": tenant.name, "schema_name": tenant.schema_name, "status": tenant.status})
            messages.success(request, "Tenant details updated.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm(instance=tenant)
    return render(request, "platform/tenant_form.html", {"form": form, "mode": "edit", "tenant": tenant})


@platform_admin_required
@require_POST
def tenant_status_update(request, pk):
    if not platform_can(request.user, "lifecycle"):
        return redirect("platform_access_denied")
    tenant = get_object_or_404(Tenant, pk=pk)
    form = TenantStatusForm(request.POST)
    if form.is_valid():
        before_status = tenant.status
        requested_status = form.cleaned_data["status"]
        subscription = getattr(tenant, "subscription", None)
        if requested_status == "active" and subscription is not None and not subscription.is_usable:
            messages.error(request, "This school cannot be reactivated while its subscription is not active or trialing. Resolve the subscription first.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
        tenant.status = requested_status
        tenant.save(update_fields=["status"])
        action = PlatformAuditEvent.TENANT_STATUS_CHANGED
        if tenant.status == "suspended":
            action = PlatformAuditEvent.TENANT_SUSPENDED
        elif before_status in {"suspended", "archived"} and tenant.status == "active":
            action = PlatformAuditEvent.TENANT_REACTIVATED
        _record_platform_event(
            request, action, tenant=tenant, object_label=tenant.name,
            before={"status": before_status}, after={"status": tenant.status},
            metadata={"reason": (form.cleaned_data.get("reason") or "").strip()},
        )
        messages.success(request, f"Tenant status updated to {tenant.status}.")
    else:
        messages.error(request, "Choose a valid tenant status.")
    return redirect("platform_tenant_detail", pk=tenant.pk)


@platform_admin_required
def domain_create(request, tenant_id):
    if not platform_can(request.user, "domains"):
        return redirect("platform_access_denied")
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    if request.method == "POST":
        form = DomainForm(request.POST)
        if form.is_valid():
            domain = form.save(commit=False)
            domain.tenant = tenant
            domain.save()
            if domain.is_primary:
                Domain.objects.filter(tenant=tenant).exclude(pk=domain.pk).update(is_primary=False)
            _record_platform_event(request, PlatformAuditEvent.DOMAIN_CREATED, tenant=tenant, domain=domain, object_label=domain.domain, after={"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary})
            messages.success(request, "Domain added.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = DomainForm()
    return render(request, "platform/domain_form.html", {"form": form, "tenant": tenant, "mode": "create"})


@platform_admin_required
def domain_edit(request, pk):
    if not platform_can(request.user, "domains"):
        return redirect("platform_access_denied")
    domain = get_object_or_404(Domain.objects.select_related("tenant"), pk=pk)
    if request.method == "POST":
        before = {"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary, "dns_status": domain.dns_status, "ssl_status": domain.ssl_status}
        form = DomainForm(request.POST, instance=domain)
        if form.is_valid():
            domain = form.save()
            if domain.is_primary:
                Domain.objects.filter(tenant=domain.tenant).exclude(pk=domain.pk).update(is_primary=False)
            _record_platform_event(request, PlatformAuditEvent.DOMAIN_UPDATED, tenant=domain.tenant, domain=domain, object_label=domain.domain, before=before, after={"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary, "dns_status": domain.dns_status, "ssl_status": domain.ssl_status})
            messages.success(request, "Domain updated.")
            return redirect("platform_tenant_detail", pk=domain.tenant.pk)
    else:
        form = DomainForm(instance=domain)
    return render(request, "platform/domain_form.html", {"form": form, "tenant": domain.tenant, "domain": domain, "mode": "edit"})


@platform_admin_required
@require_POST
def domain_mark_primary(request, pk):
    if not platform_can(request.user, "domains"):
        return redirect("platform_access_denied")
    domain = get_object_or_404(Domain.objects.select_related("tenant"), pk=pk)
    Domain.objects.filter(tenant=domain.tenant).update(is_primary=False)
    domain.is_primary = True
    domain.save(update_fields=["is_primary"])
    _record_platform_event(request, PlatformAuditEvent.DOMAIN_UPDATED, tenant=domain.tenant, domain=domain, object_label=domain.domain, after={"is_primary": True})
    messages.success(request, f"{domain.domain} is now the primary domain.")
    return redirect("platform_tenant_detail", pk=domain.tenant.pk)


@platform_admin_required
@require_POST
def domain_verify(request, pk):
    if not platform_can(request.user, "domains"):
        return redirect("platform_access_denied")
    domain = get_object_or_404(Domain.objects.select_related("tenant"), pk=pk)
    before = {"dns_status": domain.dns_status, "ssl_status": domain.ssl_status, "verified_at": str(domain.verified_at or "")}
    result = inspect_domain(domain)
    domain.last_checked_at = result["checked_at"]
    domain.dns_status = Domain.DNS_VERIFIED if result["dns_ok"] else Domain.DNS_FAILED
    domain.ssl_status = Domain.SSL_ACTIVE if result["https_ok"] else (Domain.SSL_FAILED if result["dns_ok"] else Domain.SSL_PENDING)
    if result["dns_ok"]:
        domain.verified_at = domain.verified_at or result["checked_at"]
    domain.dns_notes = "Resolved: " + (", ".join(result["resolved_ips"]) or "none") + "; expected A: " + (result["expected_ip"] or "not configured") + "; expected CNAME: " + result["expected_cname"]
    domain.save(update_fields=["dns_status", "ssl_status", "verified_at", "last_checked_at", "dns_notes"])
    _record_platform_event(request, PlatformAuditEvent.DOMAIN_VERIFIED if result["dns_ok"] else PlatformAuditEvent.DOMAIN_UPDATED, tenant=domain.tenant, domain=domain, object_label=domain.domain, before=before, after={"dns_status": domain.dns_status, "ssl_status": domain.ssl_status, "verified_at": str(domain.verified_at or "")}, metadata={"resolved_ips": result["resolved_ips"], "https_ok": result["https_ok"]})
    if result["dns_ok"] and result["https_ok"]:
        messages.success(request, "Domain is correctly pointed to EduManage and HTTPS is active.")
    elif result["dns_ok"]:
        messages.warning(request, "DNS is correct, but HTTPS is not active yet. Certificate automation must finish before handoff.")
    else:
        messages.error(request, "Domain does not yet resolve to EduManage. Review the DNS records shown below.")
    return redirect("platform_tenant_detail", pk=domain.tenant.pk)


@platform_admin_required
@require_POST
def domain_delete(request, pk):
    if not platform_can(request.user, "domains"):
        return redirect("platform_access_denied")
    domain = get_object_or_404(Domain.objects.select_related("tenant"), pk=pk)
    tenant = domain.tenant
    if domain.is_primary and not tenant.domains.exclude(pk=domain.pk).exists():
        messages.error(request, "You cannot remove the school's only primary domain. Add and verify a replacement domain first.")
        return redirect("platform_tenant_detail", pk=tenant.pk)
    before = {"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary}
    _record_platform_event(request, PlatformAuditEvent.DOMAIN_UPDATED, tenant=tenant, domain=domain, object_label=domain.domain, before=before, after={"deleted": True})
    domain.delete()
    messages.success(request, "Domain removed.")
    return redirect("platform_tenant_detail", pk=tenant.pk)
