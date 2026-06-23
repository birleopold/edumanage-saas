from decimal import Decimal

from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.filter
def format_money_amount(amount, currency_code: str = "UGX"):
    """
    Format a numeric amount with a currency code for display (e.g. invoices).
    Usage: {{ amount|format_money_amount:org_profile.default_currency }}
    """
    if amount is None:
        return "—"
    code = (currency_code or "UGX").strip().upper() or "UGX"
    try:
        val = Decimal(str(amount))
    except Exception:
        return str(amount)
    if code == "UGX":
        return f"{code} {val:,.0f}"
    return f"{code} {val:,.2f}"


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def page_with_query(request, page_number):
    """
    Build a pagination URL preserving active query parameters.
    """
    if not request:
        return f"?page={page_number}"
    query_params = request.GET.copy()
    query_params["page"] = page_number
    return f"?{query_params.urlencode()}"


def _nav_url(name: str | None = None, fallback: str = "#") -> str:
    if not name:
        return fallback
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


def _action(label: str, icon: str, *, name: str | None = None, fallback: str = "#", style: str = "secondary") -> dict:
    return {"label": label, "icon": icon, "url": _nav_url(name, fallback), "style": style}


_MODULE_QUICK_ACTIONS = (
    {
        "prefixes": ("/admin/academics/",),
        "title": "Academics navigation",
        "description": "Move quickly between academic setup, records and reports.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_course_create", "/admin/academics/courses/create/", "primary"),
            ("View All", "ph-list-bullets", "admin_course_list", "/admin/academics/courses/", "secondary"),
            ("Settings", "ph-sliders", "admin_academics_setup", "/admin/academics/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_reports_academic_performance", "/admin/reports/academic-performance/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/admin/admissions/",),
        "title": "Admissions navigation",
        "description": "Access applications, leads, forms, pipeline and reports from one place.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_admissions_applicant_create", "/admin/admissions/create/", "primary"),
            ("View All", "ph-list-bullets", "admin_admissions_applicants", "/admin/admissions/", "secondary"),
            ("Settings", "ph-sliders", "admin_admissions_form_templates", "/admin/admissions/forms/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_admissions_pipeline", "/admin/admissions/pipeline/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/admin/finance/",),
        "title": "Finance navigation",
        "description": "Jump to invoices, fee settings, reports and the main dashboard.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_invoices_create", "/admin/finance/invoices/create/", "primary"),
            ("View All", "ph-list-bullets", "admin_invoices_list", "/admin/finance/invoices/", "secondary"),
            ("Settings", "ph-sliders", "admin_fee_items_list", "/admin/finance/fee-items/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_reports_finance", "/admin/reports/finance/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/admin/hr/",),
        "title": "HR navigation",
        "description": "Manage staff, departments, positions, payroll and reports.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_hr_staff_create", "/admin/hr/staff/create/", "primary"),
            ("View All", "ph-list-bullets", "admin_hr_staff_list", "/admin/hr/", "secondary"),
            ("Settings", "ph-sliders", "admin_hr_departments_list", "/admin/hr/departments/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_reports_overview", "/admin/reports/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/admin/analytics/",),
        "title": "Analytics navigation",
        "description": "Open dashboards, records, charts and academic reports fast.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_analytics_records_setup", "/admin/analytics/records/", "primary"),
            ("View All", "ph-list-bullets", "admin_analytics_dashboard", "/admin/analytics/", "secondary"),
            ("Settings", "ph-sliders", "admin_analytics_records_setup", "/admin/analytics/records/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_reports_academic_performance", "/admin/reports/academic-performance/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/admin/settings/",),
        "title": "Organization settings navigation",
        "description": "Manage profile, campuses, feature flags and reports.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_orgsettings_campus_create", "/admin/settings/campuses/create/", "primary"),
            ("View All", "ph-list-bullets", "admin_orgsettings_campuses", "/admin/settings/campuses/", "secondary"),
            ("Settings", "ph-sliders", "admin_orgsettings_org", "/admin/settings/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_reports_overview", "/admin/reports/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/admin/enterprise/",),
        "title": "Platform controls navigation",
        "description": "Open enterprise controls, settings, reports and the dashboard.",
        "actions": (
            ("Add New", "ph-plus-circle", "admin_enterprise_permissions", "/admin/enterprise/permissions/", "primary"),
            ("View All", "ph-list-bullets", "admin_enterprise_center", "/admin/enterprise/", "secondary"),
            ("Settings", "ph-sliders", "admin_enterprise_orgsettings", "/admin/enterprise/org-settings/", "secondary"),
            ("Reports", "ph-chart-line-up", "admin_enterprise_analytics", "/admin/enterprise/analytics/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "admin_home", "/admin/", "ghost"),
        ),
    },
    {
        "prefixes": ("/platform/",),
        "title": "Platform navigation",
        "description": "Manage SaaS tenants, domains, onboarding and platform records.",
        "actions": (
            ("Add New", "ph-plus-circle", "platform_tenant_create", "/platform/tenants/create/", "primary"),
            ("View All", "ph-list-bullets", "platform_tenant_list", "/platform/tenants/", "secondary"),
            ("Settings", "ph-sliders", None, "/dj-admin/", "secondary"),
            ("Reports", "ph-chart-line-up", "platform_dashboard", "/platform/", "secondary"),
            ("Back to Dashboard", "ph-arrow-left", "platform_dashboard", "/platform/", "ghost"),
        ),
    },
)


@register.simple_tag
def admin_module_quick_actions(request):
    """Return module-level shortcut buttons for high-traffic admin areas."""
    path = getattr(request, "path", "") or ""
    for module in _MODULE_QUICK_ACTIONS:
        if any(path.startswith(prefix) for prefix in module["prefixes"]):
            return {
                "title": module["title"],
                "description": module["description"],
                "actions": [
                    _action(label, icon, name=name, fallback=fallback, style=style)
                    for label, icon, name, fallback, style in module["actions"]
                ],
            }
    return None
