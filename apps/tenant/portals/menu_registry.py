from dataclasses import dataclass, field
from typing import Iterable

from django.urls import NoReverseMatch, reverse

from apps.tenant.users.models import Role


@dataclass(frozen=True)
class MenuItem:
    label: str
    icon: str
    url_name: str | None = None
    path: str | None = None
    roles: tuple[str, ...] = (Role.ADMIN, Role.CAMPUS_ADMIN)
    badge: str | None = None

    def url(self) -> str:
        if self.path:
            return self.path
        if self.url_name:
            try:
                return reverse(self.url_name)
            except NoReverseMatch:
                return "#"
        return "#"

    def allowed_for(self, user) -> bool:
        return any(getattr(user, "has_role", lambda role: False)(role) for role in self.roles)


@dataclass(frozen=True)
class MenuSection:
    title: str
    items: tuple[MenuItem, ...] = field(default_factory=tuple)

    def visible_items(self, user) -> list[MenuItem]:
        return [item for item in self.items if item.allowed_for(user)]


ADMIN_MENU_REGISTRY: tuple[MenuSection, ...] = (
    MenuSection(
        "Command Center",
        (
            MenuItem("Dashboard", "ph-squares-four", "admin_home"),
            MenuItem("Enterprise UI Center", "ph-grid-four", "admin_enterprise_center"),
            MenuItem("Menu Registry", "ph-list-bullets", "admin_enterprise_menu_registry"),
            MenuItem("Communication Hub", "ph-chats-circle", "admin_communication_center"),
            MenuItem("System Status", "ph-heartbeat", "admin_system_status"),
        ),
    ),
    MenuSection(
        "Core School Operations",
        (
            MenuItem("Academics", "ph-books", path="/admin/academics/"),
            MenuItem("Admissions", "ph-user-plus", path="/admin/admissions/"),
            MenuItem("Students", "ph-student", path="/admin/students/"),
            MenuItem("Teachers", "ph-chalkboard-teacher", path="/admin/teachers/"),
            MenuItem("Parents", "ph-users", path="/admin/parents/"),
        ),
    ),
    MenuSection(
        "Learning and Assessment",
        (
            MenuItem("Coursework", "ph-notebook", path="/admin/coursework/"),
            MenuItem("Exams", "ph-exam", path="/admin/exams/"),
            MenuItem("Exam Review", "ph-shield-check", path="/admin/exams/review/"),
            MenuItem("Analytics", "ph-chart-line-up", "admin_enterprise_analytics"),
        ),
    ),
    MenuSection(
        "Business Operations",
        (
            MenuItem("Finance", "ph-bank", path="/admin/finance/"),
            MenuItem("Accounting Center", "ph-calculator", "admin_enterprise_accounting"),
            MenuItem("HR & Payroll", "ph-identification-badge", path="/admin/hr/"),
            MenuItem("Payroll Approvals", "ph-check-square-offset", path="/admin/hr/payroll/approvals/"),
            MenuItem("Library Operations", "ph-books", "admin_enterprise_library"),
            MenuItem("Transport", "ph-bus", path="/admin/transport/"),
        ),
    ),
    MenuSection(
        "Platform and Controls",
        (
            MenuItem("Users and Roles", "ph-user-gear", path="/admin/users/"),
            MenuItem("Permissions Center", "ph-lock-key", "admin_enterprise_permissions"),
            MenuItem("Audit & Security", "ph-shield-warning", "admin_enterprise_audit_security"),
            MenuItem("Org Settings", "ph-sliders", "admin_enterprise_orgsettings"),
            MenuItem("Integrations", "ph-plugs-connected", path="/admin/integrations/"),
        ),
    ),
)


def visible_admin_menu(user) -> list[dict]:
    sections = []
    for section in ADMIN_MENU_REGISTRY:
        items = section.visible_items(user)
        if items:
            sections.append({"title": section.title, "items": items})
    return sections
