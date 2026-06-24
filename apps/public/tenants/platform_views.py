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
from .models import Domain, Tenant


PLATFORM_PAGE_SIZE = 25
PLATFORM_CNAME_TARGET = "edumanage.com"
PLATFORM_A_RECORD_TARGET = "YOUR_EDUMANAGE_SERVER_IP"


def _login_redirect_url(request):
    query = urlencode({"next": request.get_full_path()})
    return f"{reverse('platform_admin_login')}?{query}"


def _safe_next_url(request):
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def platform_admin_required(view_func):
    """Allow only authenticated platform superusers to use the public SaaS console."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(_login_redirect_url(request))
        if not request.user.is_superuser:
            messages.error(request, "Only platform super administrators can access the SaaS console.")
            return redirect("platform_admin_login")
        return view_func(request, *args, **kwargs)

    return _wrapped


def _parse_per_page(request, default=PLATFORM_PAGE_SIZE, max_value=100):
    try:
        return max(1, min(int(request.GET.get("per_page") or default), max_value))
    except (TypeError, ValueError):
        return default


def _schema_status(schema_name):
    if connection.vendor != "postgresql":
        return {"label": "Not checked", "exists": None, "detail": "Schema checks are available in PostgreSQL tenant mode."}
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s LIMIT 1",
                [schema_name],
            )
            exists = cursor.fetchone() is not None
    except Exception as exc:  # pragma: no cover - defensive for restricted database users
        return {"label": "Unknown", "exists": None, "detail": str(exc)}
    return {
        "label": "Ready" if exists else "Missing",
        "exists": exists,
        "detail": "Schema exists." if exists else "No PostgreSQL schema found for this tenant.",
    }


def _domain_dns_instructions(domain: Domain) -> dict:
    if domain.type == Domain.SUBDOMAIN:
        return {
            "summary": f"Create a CNAME record for {domain.domain} pointing to the EduManage platform host.",
            "records": [
                {"type": "CNAME", "host": domain.domain, "value": PLATFORM_CNAME_TARGET},
            ],
            "example": "schoolname.edumanage.com",
        }
    return {
        "summary": "Point the custom domain to EduManage, then keep it unchanged while SSL is issued.",
        "records": [
            {"type": "A", "host": "@", "value": PLATFORM_A_RECORD_TARGET},
            {"type": "CNAME", "host": "www", "value": PLATFORM_CNAME_TARGET},
        ],
        "example": "schoolname.ac.ug",
    }


def _domain_management_rows(domains):
    return [
        {
            "domain": domain,
            "dns": _domain_dns_instructions(domain),
            "verification_label": "Verified" if domain.is_verified else "Pending",
            "ssl_label": domain.get_ssl_status_display(),
            "dns_label": domain.get_dns_status_display(),
        }
        for domain in domains
    ]


def platform_login(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("platform_dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if not user.is_superuser:
                messages.error(request, "This console is restricted to platform super administrators.")
            else:
                login(request, user)
                messages.success(request, "Welcome to the Platform Admin Console.")
                return redirect(_safe_next_url(request) or "platform_dashboard")
        else:
            messages.error(request, "Please check your username and password.")

    return render(request, "platform/login.html", {"form": form})


@platform_admin_required
def platform_logout(request):
    logout(request)
    messages.success(request, "You have signed out of the Platform Admin Console.")
    return redirect("platform_admin_login")


@platform_admin_required
def dashboard(request):
    status_counts = Tenant.objects.values("status").annotate(total=Count("id")).order_by("status")
    tenants = Tenant.objects.order_by("name")[:8]
    domains = Domain.objects.select_related("tenant").order_by("-is_primary", "domain")[:10]
    context = {
        "tenant_count": Tenant.objects.count(),
        "active_count": Tenant.objects.filter(status="active").count(),
        "suspended_count": Tenant.objects.filter(status="suspended").count(),
        "domain_count": Domain.objects.count(),
        "verified_domain_count": Domain.objects.filter(verified_at__isnull=False).count(),
        "status_counts": status_counts,
        "tenants": tenants,
        "domains": domains,
    }
    return render(request, "platform/dashboard.html", context)


@platform_admin_required
def tenant_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Tenant.objects.annotate(domain_count=Count("domains")).order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(schema_name__icontains=q) | Q(domains__domain__icontains=q)).distinct()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "platform/tenant_list.html",
        {"tenants": page_obj.object_list, "page_obj": page_obj, "q": q, "status": status, "per_page": per_page},
    )


@platform_admin_required
def tenant_create(request):
    if request.method == "POST":
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            onboarding = getattr(form, "onboarding_result", None)
            if onboarding:
                messages.success(
                    request,
                    (
                        f"School '{tenant.name}' fully onboarded: tenant, primary domain, organization profile, "
                        "main campus, owner admin account, feature flags, and current academic period were created."
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
    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            tenant = form.save()
            messages.success(request, f"Tenant '{tenant.name}' updated.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm(instance=tenant)
    return render(request, "platform/tenant_form.html", {"form": form, "mode": "edit", "tenant": tenant})


@platform_admin_required
def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    domains = list(tenant.domains.order_by("-is_primary", "domain"))
    return render(
        request,
        "platform/tenant_detail.html",
        {
            "tenant": tenant,
            "domains": domains,
            "domain_management": _domain_management_rows(domains),
            "schema_status": _schema_status(tenant.schema_name),
            "status_form": TenantStatusForm(initial={"status": tenant.status}),
        },
    )


@platform_admin_required
@require_POST
def tenant_status_update(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    form = TenantStatusForm(request.POST)
    if form.is_valid():
        tenant.status = form.cleaned_data["status"]
        tenant.save(update_fields=["status"])
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
            messages.success(request, f"Domain '{domain.domain}' added.")
            return redirect("platform_tenant_detail", pk=tenant.pk)
    else:
        form = DomainForm(tenant=tenant)
    return render(request, "platform/domain_form.html", {"form": form, "tenant": tenant})


@platform_admin_required
def domain_edit(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    if request.method == "POST":
        form = DomainForm(request.POST, instance=domain)
        if form.is_valid():
            domain = form.save()
            messages.success(request, f"Domain '{domain.domain}' updated.")
            return redirect("platform_tenant_detail", pk=domain.tenant_id)
    else:
        form = DomainForm(instance=domain)
    return render(request, "platform/domain_form.html", {"form": form, "tenant": domain.tenant, "domain": domain})


@platform_admin_required
@require_POST
def domain_mark_primary(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    Domain.objects.filter(tenant=domain.tenant).exclude(pk=domain.pk).update(is_primary=False)
    domain.is_primary = True
    domain.save(update_fields=["is_primary"])
    messages.success(request, f"'{domain.domain}' is now the primary domain.")
    return redirect("platform_tenant_detail", pk=domain.tenant_id)


@platform_admin_required
@require_POST
def domain_verify(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    action = request.POST.get("action") or "dns_verified"
    update_fields = ["last_checked_at"]
    domain.last_checked_at = timezone.now()

    if action == "dns_failed":
        domain.dns_status = Domain.DNS_FAILED
        update_fields.append("dns_status")
        messages.error(request, f"DNS check failed for '{domain.domain}'.")
    elif action == "ssl_active":
        domain.ssl_status = Domain.SSL_ACTIVE
        update_fields.append("ssl_status")
        messages.success(request, f"SSL marked active for '{domain.domain}'.")
    elif action == "ssl_failed":
        domain.ssl_status = Domain.SSL_FAILED
        update_fields.append("ssl_status")
        messages.error(request, f"SSL marked failed for '{domain.domain}'.")
    else:
        domain.dns_status = Domain.DNS_VERIFIED
        domain.verified_at = timezone.now()
        update_fields.extend(["dns_status", "verified_at"])
        messages.success(request, f"Domain '{domain.domain}' marked as DNS verified.")

    domain.save(update_fields=sorted(set(update_fields)))
    return redirect("platform_tenant_detail", pk=domain.tenant_id)


@platform_admin_required
@require_POST
def domain_delete(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    tenant_id = domain.tenant_id
    if domain.is_primary and domain.tenant.domains.count() > 1:
        messages.error(request, "Set another primary domain before deleting this one.")
        return redirect("platform_tenant_detail", pk=tenant_id)
    messages.success(request, f"Domain '{domain.domain}' deleted.")
    domain.delete()
    return redirect("platform_tenant_detail", pk=tenant_id)
