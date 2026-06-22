from dataclasses import dataclass

from django.apps import apps
from django.contrib.auth.models import Group
from django.shortcuts import render

from .menu_registry import visible_admin_menu
from .permissions import admin_portal_required


@dataclass(frozen=True)
class ModelCard:
    app_label: str
    model_name: str
    label: str
    route: str | None = None
    admin_path: str | None = None


def _count(app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return None
    try:
        return model.objects.count()
    except Exception:
        return None


def _cards(items):
    cards = []
    for item in items:
        total = Group.objects.count() if item.app_label == "auth" and item.model_name == "Group" else _count(item.app_label, item.model_name)
        cards.append({"item": item, "count": total})
    return cards


ANALYTICS_MODELS = (
    ModelCard("analytics", "AtRiskAlert", "At-risk alerts", "/admin/analytics/"),
    ModelCard("analytics", "ClassPerformanceReport", "Class reports", "/admin/analytics/"),
    ModelCard("analytics", "PerformanceTrend", "Performance trends", "/admin/analytics/"),
    ModelCard("analytics", "StudentPerformanceSnapshot", "Student snapshots", "/admin/analytics/"),
    ModelCard("analytics", "SubjectPerformance", "Subject performance", "/admin/analytics/"),
    ModelCard("analytics", "TeacherPerformanceMetrics", "Teacher metrics", "/admin/analytics/"),
)

AUDIT_MODELS = (
    ModelCard("audit", "AuditEvent", "Audit events", "/admin/audit/"),
    ModelCard("audit", "BackupJob", "Backup jobs", "/dj-admin/audit/backupjob/"),
    ModelCard("audit", "ConsentRecord", "Consent records", "/dj-admin/audit/consentrecord/"),
    ModelCard("audit", "DataRetentionPolicy", "Retention policies", "/dj-admin/audit/dataretentionpolicy/"),
    ModelCard("audit", "ExportPermission", "Export permissions", "/dj-admin/audit/exportpermission/"),
    ModelCard("audit", "LoginHistory", "Login history", "/dj-admin/audit/loginhistory/"),
    ModelCard("audit", "SuspiciousLoginAlert", "Suspicious login alerts", "/dj-admin/audit/suspiciousloginalert/"),
    ModelCard("audit", "UserTwoFactorSettings", "2FA settings", "/dj-admin/audit/usertwofactorsettings/"),
)

ACCOUNTING_MODELS = (
    ModelCard("finance", "Account", "Accounts", "/dj-admin/finance/account/"),
    ModelCard("finance", "JournalEntry", "Journal entries", "/dj-admin/finance/journalentry/"),
    ModelCard("finance", "BankReconciliation", "Bank reconciliations", "/dj-admin/finance/bankreconciliation/"),
    ModelCard("finance", "BankStatementLine", "Bank statement lines", "/dj-admin/finance/bankstatementline/"),
    ModelCard("finance", "DuplicatePaymentAlert", "Duplicate payment alerts", "/dj-admin/finance/duplicatepaymentalert/"),
    ModelCard("finance", "ExpenseCategory", "Expense categories", "/dj-admin/finance/expensecategory/"),
    ModelCard("finance", "SchoolExpense", "School expenses", "/admin/finance/"),
)

LIBRARY_MODELS = (
    ModelCard("library", "Book", "Books", "/admin/library/"),
    ModelCard("library", "BookCopy", "Book copies", "/admin/library/"),
    ModelCard("library", "BookLoan", "Loans", "/admin/library/"),
    ModelCard("library", "Reservation", "Reservations", "/admin/library/"),
    ModelCard("library", "Fine", "Fines", "/admin/library/"),
    ModelCard("library", "Author", "Authors", "/dj-admin/library/author/"),
    ModelCard("library", "Category", "Categories", "/dj-admin/library/category/"),
)

ORG_MODELS = (
    ModelCard("orgsettings", "OrganizationProfile", "Organization profile", "/admin/settings/"),
    ModelCard("orgsettings", "Campus", "Campuses", "/admin/settings/"),
    ModelCard("orgsettings", "FeatureFlag", "Feature flags", "/dj-admin/orgsettings/featureflag/"),
    ModelCard("orgsettings", "Notification", "Notifications", "/notifications/"),
    ModelCard("orgsettings", "ActionLog", "Action logs", "/admin/audit/"),
    ModelCard("orgsettings", "StatusHistory", "Status history", "/admin/audit/"),
)

PERMISSION_MODELS = (
    ModelCard("users", "User", "Users", "/admin/users/"),
    ModelCard("users", "Role", "Roles", "/admin/users/"),
    ModelCard("users", "UserRole", "User roles", "/admin/users/"),
    ModelCard("auth", "Group", "Django groups", "/dj-admin/auth/group/"),
    ModelCard("users", "MobileDevice", "Mobile devices", "/admin/users/devices/"),
)


def _render_center(request, title, subtitle, items, template="portals/admin/enterprise/center.html"):
    return render(request, template, {"title": title, "subtitle": subtitle, "cards": _cards(items)})


@admin_portal_required
def enterprise_center(request):
    groups = [
        {"title": "Analytics", "url": "/admin/enterprise/analytics/", "description": "Drill-down entry point for performance and risk models."},
        {"title": "Audit & Security", "url": "/admin/enterprise/audit-security/", "description": "Backup, retention, login history, 2FA and suspicious login controls."},
        {"title": "Accounting", "url": "/admin/enterprise/accounting/", "description": "Deep accounting records not usually used by teachers or parents."},
        {"title": "Library Operations", "url": "/admin/enterprise/library/", "description": "Loans, reservations, fines, copies, categories and authors."},
        {"title": "Org Settings", "url": "/admin/enterprise/org-settings/", "description": "Campus, feature flags, notifications and status/action records."},
        {"title": "Permissions", "url": "/admin/enterprise/permissions/", "description": "Users, roles, user-role mappings, groups and devices."},
        {"title": "Menu Registry", "url": "/admin/enterprise/menu/", "description": "Central role-aware navigation registry for the admin portal."},
        {"title": "UI Components", "url": "/admin/enterprise/ui-components/", "description": "Reusable card, filter, list and detail patterns for future modules."},
    ]
    return render(request, "portals/admin/enterprise/index.html", {"groups": groups})


@admin_portal_required
def analytics_center(request):
    return _render_center(request, "Analytics Drill-down", "Performance, trends, snapshots and risk signals.", ANALYTICS_MODELS)


@admin_portal_required
def audit_security_center(request):
    return _render_center(request, "Audit & Security Center", "Operational security records and compliance controls.", AUDIT_MODELS)


@admin_portal_required
def accounting_center(request):
    return _render_center(request, "Accounting Center", "Finance back-office records with dj-admin fallbacks where needed.", ACCOUNTING_MODELS)


@admin_portal_required
def library_center(request):
    return _render_center(request, "Library Operations", "Books, copies, loans, reservations and fines.", LIBRARY_MODELS)


@admin_portal_required
def orgsettings_center(request):
    return _render_center(request, "Organization Settings Center", "Organization, campus, feature flag and notification records.", ORG_MODELS)


@admin_portal_required
def permissions_center(request):
    return _render_center(request, "Permissions Center", "Users, roles, groups and device access.", PERMISSION_MODELS)


@admin_portal_required
def menu_registry_view(request):
    return render(request, "portals/admin/enterprise/menu_registry.html", {"sections": visible_admin_menu(request.user)})


@admin_portal_required
def ui_components_view(request):
    samples = [
        {"title": "List page", "description": "Title, filter bar, table/list, status badges, pagination."},
        {"title": "Detail page", "description": "Summary cards, related records, action rail and audit timeline."},
        {"title": "Filter bar", "description": "Search, status, date range and export actions."},
        {"title": "Audit timeline", "description": "Actor, action, comments, status change and timestamp."},
    ]
    return render(request, "portals/admin/enterprise/ui_components.html", {"samples": samples})
