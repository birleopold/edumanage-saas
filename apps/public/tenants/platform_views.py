from functools import wraps
from urllib.parse import urlencode

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
from .models import Domain, PlatformAuditEvent, Tenant
from .subscription_services import create_subscription_for_tenant


PLATFORM_PAGE_SIZE = 25
PLATFORM_CNAME_TARGET = "edumanage.com"
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
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if request.user.is_authenticated:
            messages.error(request, "Only platform superusers can access the SaaS management console.")
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
    return PlatformAuditEvent.objects.create(
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
        {
            "title": "Tenant activated",
            "description": "School status allows users into the tenant portal.",
            "done": tenant.status == "active",
            "detail": tenant.status.title(),
        },
        {
            "title": "Primary login domain assigned",
            "description": "The school has a primary web address for first login.",
            "done": primary_domain is not None,
            "detail": getattr(primary_domain, "domain", "No domain"),
        },
        {
            "title": "DNS verified",
            "description": "DNS has been checked before the school is sent live credentials.",
            "done": bool(primary_domain and primary_domain.is_verified),
            "detail": primary_domain.get_dns_status_display() if primary_domain else "Pending",
        },
        {
            "title": "SSL active",
            "description": "The login address is ready for secure browser access.",
            "done": bool(primary_domain and primary_domain.is_ssl_active),
            "detail": primary_domain.get_ssl_status_display() if primary_domain else "Pending",
        },
        {
            "title": "Subscription usable",
            "description": "Billing state permits the school to operate.",
            "done": bool(subscription and subscription.is_usable),
            "detail": subscription.get_status_display() if subscription else "Missing",
        },
        {
            "title": "Owner first-login path ready",
            "description": "Platform staff can hand the owner their username, login URL and setup checklist.",
            "done": bool(metadata.get("admin_username") and login_url and setup_guide_url),
            "detail": metadata.get("admin_username") or "Not recorded",
        },
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
    if domain.type == Domain.SUBDOMAIN:
        return {
            "summary": "Point this EduManage subdomain to the platform host.",
            "records": [{"type": "CNAME", "host": domain.domain, "value": PLATFORM_CNAME_TARGET}],
            "example": "schoolname.edumanage.com",
        }
    return {
        "summary": "Point the custom school domain to EduManage using A/CNAME records.",
        "records": [
            {"type": "A", "host": "@", "value": PLATFORM_A_RECORD_TARGET},
            {"type": "CNAME", "host": "www", "value": PLATFORM_CNAME_TARGET},
        ],
        "example": "schoolname.ac.ug",
    }


def _domain_management_rows(domains):
    rows = []
    for domain in domains:
        rows.append(
            {
                "domain": domain,
                "dns": _domain_dns_instructions(domain),
                "dns_label": domain.get_dns_status_display(),
                "ssl_label": domain.get_ssl_status_display(),
            }
        )
    return rows


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


@platform_admin_required
def platform_login(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect(_safe_next_url(request) or reverse("platform_dashboard"))
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not user.is_superuser:
            messages.error(request, "This account is not allowed to access the Platform Console.")
        else:
            login(request, user)
            messages.success(request, "Welcome to the Platform Console.")
            return redirect(_safe_next_url(request) or reverse("platform_dashboard"))
    return render(request, "platform/login.html", {"form": form, "next": request.GET.get("next", "")})


@platform_admin_required
def platform_logout(request):
    logout(request)
    messages.info(request, "You have signed out of the Platform Console.")
    return redirect("platform_admin_login")


@platform_admin_required
def dashboard(request):
    tenants = Tenant.objects.order_by("-created_at")[:8]
    domains = Domain.objects.select_related("tenant").order_by("-is_primary", "domain")[:10]
    recent_platform_events = PlatformAuditEvent.objects.select_related("actor", "tenant", "domain")[:8]
    return render(
        request,
        "platform/dashboard.html",
        {
            "tenant_count": Tenant.objects.count(),
            "active_count": Tenant.objects.filter(status="active").count(),
            "suspended_count": Tenant.objects.filter(status="suspended").count(),
            "domain_count": Domain.objects.count(),
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
    return render(
        request,
        "platform/activity.html",
        {
            "page_obj": page_obj,
            "events": page_obj.object_list,
            "actions": PlatformAuditEvent.ACTION_CHOICES,
            "tenants": Tenant.objects.order_by("name"),
            "summary_cards": _activity_summary_cards(),
            "selected_action": request.GET.get("action", ""),
            "selected_tenant": request.GET.get("tenant", ""),
            "search_query": request.GET.get("q", ""),
        },
    )


@platform_admin_required
def tenant_list(request):
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    tenants = Tenant.objects.order_by("-created_at")
    if status:
        tenants = tenants.filter(status=status)
    if q:
        tenants = tenants.filter(Q(name__icontains=q) | Q(schema_name__icontains=q) | Q(domains__domain__icontains=q)).distinct()
    paginator = Paginator(tenants, PLATFORM_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "platform/tenant_list.html",
        {"page_obj": page_obj, "tenants": page_obj.object_list, "status": status, "q": q, "statuses": ["active", "pending", "suspended", "archived"]},
    )


@platform_admin_required
def tenant_create(request):
    if request.method == "POST":
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            onboarding = getattr(form, "onboarding_result", None)
            subscription = getattr(form, "subscription_result", None)
            primary_domain = tenant.domains.filter(is_primary=True).first()
            onboarding_metadata = _onboarding_event_metadata(onboarding) if onboarding else {}
            _record_platform_event(
                request,
                PlatformAuditEvent.TENANT_CREATED,
                tenant=tenant,
                domain=primary_domain,
                object_label=tenant.name,
                after={"name": tenant.name, "schema_name": tenant.schema_name, "status": tenant.status, "primary_domain": getattr(primary_domain, "domain", "")},
                metadata=onboarding_metadata,
            )
            if subscription:
                _record_platform_event(
                    request,
                    PlatformAuditEvent.SUBSCRIPTION_CREATED,
                    tenant=tenant,
                    domain=primary_domain,
                    object_label=f"{tenant.name} subscription",
                    after={"plan": subscription.plan.code, "status": subscription.status, "amount": str(subscription.amount), "billing_cycle": subscription.billing_cycle},
                )
            if onboarding:
                messages.success(
                    request,
                    (
                        f"School '{tenant.name}' fully onboarded: tenant, primary domain, organization profile, "
                        "main campus, owner admin account, feature flags, subscription, and current academic period were created."
                    ),
                )
                messages.info(
                    request,
                    f"Admin username: {onboarding.admin_user.username}. Login domain: {onboarding.login_domain}.",
                )
            else:
                messages.success(request, f"Tenant '{tenant.name}' created with its primary custom domain.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm()
    return render(request, "platform/tenant_form.html", {"form": form, "mode": "create"})


@platform_admin_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    before = {"name": tenant.name, "status": tenant.status, "schema_name": tenant.schema_name}
    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            tenant = form.save()
            _record_platform_event(
                request,
                PlatformAuditEvent.TENANT_STATUS_CHANGED,
                tenant=tenant,
                object_label=tenant.name,
                before=before,
                after={"name": tenant.name, "status": tenant.status, "schema_name": tenant.schema_name},
            )
            messages.success(request, f"Tenant '{tenant.name}' updated.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm(instance=tenant)
    return render(request, "platform/tenant_form.html", {"form": form, "mode": "edit", "tenant": tenant})


@platform_admin_required
def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    domains = list(tenant.domains.order_by("-is_primary", "domain"))
    subscription = getattr(tenant, "subscription", None)
    if subscription is None:
        subscription = create_subscription_for_tenant(tenant)
    return render(
        request,
        "platform/tenant_detail.html",
        {
            "tenant": tenant,
            "domains": domains,
            "subscription": subscription,
            "domain_management": _domain_management_rows(domains),
            "onboarding_handoff": _tenant_onboarding_handoff(tenant, domains, subscription),
            "schema_status": _schema_status(tenant.schema_name),
            "status_form": TenantStatusForm(initial={"status": tenant.status}),
            "recent_platform_events": PlatformAuditEvent.objects.select_related("actor", "tenant", "domain").filter(tenant=tenant)[:20],
        },
    )


@platform_admin_required
@require_POST
def tenant_status_update(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    old_status = tenant.status
    form = TenantStatusForm(request.POST)
    if form.is_valid():
        new_status = form.cleaned_data["status"]
        tenant.status = new_status
        tenant.save(update_fields=["status"])
        if new_status == "suspended":
            audit_action = PlatformAuditEvent.TENANT_SUSPENDED
        elif old_status == "suspended" and new_status == "active":
            audit_action = PlatformAuditEvent.TENANT_REACTIVATED
        else:
            audit_action = PlatformAuditEvent.TENANT_STATUS_CHANGED
        _record_platform_event(
            request,
            audit_action,
            tenant=tenant,
            object_label=tenant.name,
            before={"status": old_status},
            after={"status": new_status},
            metadata={"reason": form.cleaned_data.get("reason", "")},
        )
        messages.success(request, f"Tenant status updated to {tenant.status}.")
    else:
        messages.error(request, "Invalid status update.")
    return redirect("platform_tenant_detail", pk=tenant.pk)


@platform_admin_required
def domain_create(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    if request.method == "POST":
        form = DomainForm(request.POST, tenant=tenant)
        if form.is_valid():
            domain = form.save()
            _record_platform_event(
                request,
                PlatformAuditEvent.DOMAIN_CREATED,
                tenant=tenant,
                domain=domain,
                object_label=domain.domain,
                after={"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary},
            )
            messages.success(request, f"Domain '{domain.domain}' added.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = DomainForm(tenant=tenant)
    return render(request, "platform/domain_form.html", {"form": form, "tenant": tenant})


@platform_admin_required
def domain_edit(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    before = {"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary, "dns_status": domain.dns_status, "ssl_status": domain.ssl_status}
    if request.method == "POST":
        form = DomainForm(request.POST, instance=domain)
        if form.is_valid():
            domain = form.save()
            _record_platform_event(
                request,
                PlatformAuditEvent.DOMAIN_UPDATED,
                tenant=domain.tenant,
                domain=domain,
                object_label=domain.domain,
                before=before,
                after={"domain": domain.domain, "type": domain.type, "is_primary": domain.is_primary, "dns_status": domain.dns_status, "ssl_status": domain.ssl_status},
            )
            messages.success(request, f"Domain '{domain.domain}' updated.")
            return redirect("platform_tenant_detail", pk=domain.tenant_id)
    else:
        form = DomainForm(instance=domain)
    return render(request, "platform/domain_form.html", {"form": form, "tenant": domain.tenant, "domain": domain})


@platform_admin_required
@require_POST
def domain_mark_primary(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    Domain.objects.filter(tenant=domain.tenant, is_primary=True).exclude(pk=domain.pk).update(is_primary=False)
    before = {"is_primary": domain.is_primary}
    domain.is_primary = True
    domain.save(update_fields=["is_primary"])
    _record_platform_event(
        request,
        PlatformAuditEvent.DOMAIN_UPDATED,
        tenant=domain.tenant,
        domain=domain,
        object_label=domain.domain,
        before=before,
        after={"is_primary": True},
        metadata={"primary_domain_changed": True},
    )
    messages.success(request, f"{domain.domain} is now the primary domain.")
    return redirect("platform_tenant_detail", pk=domain.tenant_id)


@platform_admin_required
@require_POST
def domain_verify(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    action = request.POST.get("action", "dns_verified")
    before = {"dns_status": domain.dns_status, "ssl_status": domain.ssl_status, "verified_at": str(domain.verified_at or "")}
    audit_action = PlatformAuditEvent.DOMAIN_VERIFIED
    if action == "dns_failed":
        domain.dns_status = Domain.DNS_FAILED
        domain.dns_notes = request.POST.get("dns_notes", domain.dns_notes)
        message = f"DNS verification failed for {domain.domain}."
    elif action == "ssl_active":
        domain.ssl_status = Domain.SSL_ACTIVE
        audit_action = PlatformAuditEvent.DOMAIN_SSL_UPDATED
        message = f"SSL marked active for {domain.domain}."
    elif action == "ssl_failed":
        domain.ssl_status = Domain.SSL_FAILED
        audit_action = PlatformAuditEvent.DOMAIN_SSL_UPDATED
        message = f"SSL marked failed for {domain.domain}."
    else:
        domain.dns_status = Domain.DNS_VERIFIED
        domain.verified_at = timezone.now()
        message = f"DNS verified for {domain.domain}."
    domain.last_checked_at = timezone.now()
    domain.save(update_fields=["dns_status", "ssl_status", "verified_at", "last_checked_at", "dns_notes"])
    _record_platform_event(
        request,
        audit_action,
        tenant=domain.tenant,
        domain=domain,
        object_label=domain.domain,
        before=before,
        after={"dns_status": domain.dns_status, "ssl_status": domain.ssl_status, "verified_at": str(domain.verified_at or "")},
        metadata={"action": action},
    )
    messages.success(request, message)
    return redirect("platform_tenant_detail", pk=domain.tenant_id)


@platform_admin_required
@require_POST
def domain_delete(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    tenant_id = domain.tenant_id
    label = domain.domain
    _record_platform_event(
        request,
        PlatformAuditEvent.DOMAIN_UPDATED,
        tenant=domain.tenant,
        domain=domain,
        object_label=label,
        before={"domain": label, "deleted": False},
        after={"domain": label, "deleted": True},
        metadata={"domain_deleted": True},
    )
    domain.delete()
    messages.success(request, f"Domain '{label}' removed.")
    return redirect("platform_tenant_detail", pk=tenant_id)
