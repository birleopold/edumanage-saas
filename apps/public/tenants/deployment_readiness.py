from django.conf import settings
from django.db import connection
from django.shortcuts import render

from apps.public.tenants.models import Domain, Tenant

from .platform_views import PLATFORM_A_RECORD_TARGET, PLATFORM_CNAME_TARGET, platform_admin_required


PRIORITY_SECTIONS = [
    {
        "key": "postgresql-tenancy",
        "priority": 1,
        "title": "Production PostgreSQL tenant setup",
        "icon": "ph-database",
        "why": "Nothing should go to real clients until tenant schemas are running on PostgreSQL and migrations are repeatable.",
        "checks": [
            "Use config.settings.tenants in production.",
            "Set POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST and POSTGRES_PORT.",
            "Run shared migrations before tenant migrations.",
            "Confirm each active tenant has a PostgreSQL schema.",
            "Create a rollback plan before tenant migrations.",
        ],
    },
    {
        "key": "environment-variables",
        "priority": 2,
        "title": "Environment variables",
        "icon": "ph-sliders",
        "why": "Secrets, domains, email/SMS keys and deployment switches must be outside code before production.",
        "checks": [
            "DJANGO_SECRET_KEY is strong and private.",
            "DJANGO_DEBUG is false.",
            "DJANGO_ALLOWED_HOSTS contains production domains only.",
            "DATABASE, email, SMS, webhook and web-push variables are configured.",
            "No real passwords or API keys are committed to Git.",
        ],
    },
    {
        "key": "domain-routing",
        "priority": 3,
        "title": "Domain routing",
        "icon": "ph-globe",
        "why": "Schools must resolve to the right tenant using subdomains or verified custom domains.",
        "checks": [
            "Primary platform domain points to the app server/load balancer.",
            "Wildcard/subdomain routing is configured for schoolname.edumanage.com style domains.",
            "Custom domains have A/CNAME DNS instructions documented.",
            "Domain verification flow is tested before onboarding real schools.",
            "Invalid domains show the friendly invalid-domain page.",
        ],
    },
    {
        "key": "ssl-certificates",
        "priority": 4,
        "title": "SSL certificates",
        "icon": "ph-shield-check",
        "why": "PWA install, logins, payments and school trust all require HTTPS.",
        "checks": [
            "HTTPS is enforced at the proxy/load balancer.",
            "Main platform certificate is valid.",
            "Wildcard or automated per-domain certificates are planned.",
            "SSL status is tracked on domain records.",
            "Certificate renewal alerts are configured.",
        ],
    },
    {
        "key": "backups",
        "priority": 5,
        "title": "Backups and restore drills",
        "icon": "ph-archive-box",
        "why": "Schools will trust the system only if data can be recovered after mistakes or outages.",
        "checks": [
            "Nightly PostgreSQL backups are automated.",
            "Backups are encrypted and stored off-server.",
            "Tenant-level export/backup tools are available.",
            "A restore test has been performed on a separate environment.",
            "Retention policy is documented.",
        ],
    },
    {
        "key": "admin-security",
        "priority": 6,
        "title": "Admin security",
        "icon": "ph-lock-key",
        "why": "Platform-owner and school-admin accounts control sensitive student, finance and tenant data.",
        "checks": [
            "Only trusted superusers can access the Platform Console.",
            "Admin 2FA policy is enabled for production.",
            "Default accounts/passwords are removed.",
            "Owner accounts must change temporary passwords on first login.",
            "Audit logs are enabled and visible.",
        ],
    },
    {
        "key": "monitoring",
        "priority": 7,
        "title": "Monitoring and uptime checks",
        "icon": "ph-pulse",
        "why": "You need to know when the platform is slow, unavailable or failing before schools complain.",
        "checks": [
            "Health endpoint is monitored externally.",
            "Server CPU, memory, disk and database size are monitored.",
            "Disk-space alerts are configured for backups and media.",
            "Application response time is tracked.",
            "On-call/contact process is defined.",
        ],
    },
    {
        "key": "error-logging",
        "priority": 8,
        "title": "Error logging",
        "icon": "ph-bug",
        "why": "Friendly error pages help users, but developers still need detailed logs to fix issues quickly.",
        "checks": [
            "Server logs are retained and searchable.",
            "Django errors are captured with stack traces outside the user UI.",
            "Email or external alerts are configured for 500 errors.",
            "Request IDs or timestamps are available for support.",
            "Sensitive data is not printed in logs.",
        ],
    },
    {
        "key": "email-sms-providers",
        "priority": 9,
        "title": "Email/SMS provider setup",
        "icon": "ph-paper-plane-tilt",
        "why": "Onboarding, password resets, fee reminders and parent communication need reliable providers.",
        "checks": [
            "SMTP provider is configured and tested.",
            "Password-reset emails are tested end to end.",
            "SMS gateway credentials and sender ID are configured.",
            "Fee reminder channels are tested with a small pilot group.",
            "Provider failure handling is documented.",
        ],
    },
    {
        "key": "final-go-live",
        "priority": 10,
        "title": "Final go-live rehearsal",
        "icon": "ph-rocket-launch",
        "why": "A rehearsal confirms the whole SaaS flow works before taking money from real schools.",
        "checks": [
            "Create a test tenant from the Platform Console.",
            "Add owner admin and complete first login.",
            "Verify domain, SSL, exports, reports and audit logs.",
            "Run backup and restore test.",
            "Document support contacts and launch checklist sign-off.",
        ],
    },
]


def _env_check(name, *, required=True):
    value = getattr(settings, name, None)
    configured = bool(value) and value not in {"*", "unsafe-dev-key", "YOUR_EDUMANAGE_SERVER_IP"}
    if name == "DEBUG":
        configured = value is False
    return {"name": name, "configured": configured, "required": required, "value": "Configured" if configured else "Needs attention"}


def _database_status():
    is_postgres = connection.vendor == "postgresql"
    return {
        "label": "PostgreSQL" if is_postgres else connection.vendor,
        "ready": is_postgres,
        "detail": "Production tenant schemas require PostgreSQL." if not is_postgres else "PostgreSQL tenant database is active.",
    }


def _readiness_score(env_checks, database_status, domains_ready):
    total = len(env_checks) + 2
    ready = sum(1 for item in env_checks if item["configured"])
    ready += 1 if database_status["ready"] else 0
    ready += 1 if domains_ready else 0
    return round((ready / total) * 100) if total else 0


@platform_admin_required
def deployment_readiness(request):
    env_checks = [
        _env_check("SECRET_KEY"),
        _env_check("DEBUG"),
        _env_check("ALLOWED_HOSTS"),
        _env_check("EMAIL_HOST", required=False),
        _env_check("DEFAULT_FROM_EMAIL", required=False),
        _env_check("SMS_GATEWAY_URL", required=False),
        _env_check("WEB_PUSH_PUBLIC_KEY", required=False),
    ]
    database_status = _database_status()
    domains_ready = Domain.objects.filter(is_primary=True).exists()
    context = {
        "priority_sections": PRIORITY_SECTIONS,
        "database_status": database_status,
        "env_checks": env_checks,
        "readiness_score": _readiness_score(env_checks, database_status, domains_ready),
        "tenant_count": Tenant.objects.count(),
        "active_tenant_count": Tenant.objects.filter(status="active").count(),
        "domain_count": Domain.objects.count(),
        "verified_domain_count": Domain.objects.filter(verified_at__isnull=False).count(),
        "domains_ready": domains_ready,
        "cname_target": PLATFORM_CNAME_TARGET,
        "a_record_target": PLATFORM_A_RECORD_TARGET,
    }
    return render(request, "platform/deployment_readiness.html", context)
