import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


REQUIRED_TEST_EVIDENCE = {
    "Finance campus scope": ("apps/tenant/finance/tests.py", "FinanceAdminCampusScopeTests"),
    "Assessments campus scope": ("apps/tenant/assessments/tests/test_admin_campus_scope.py", "AssessmentAdminCampusScopeTests"),
    "Attendance campus scope": ("apps/tenant/attendance/tests.py", "AttendanceAdminCampusScopeTests"),
    "Sickbay campus scope": ("apps/tenant/sickbay/tests.py", "Hidden fever"),
    "Documents/self-service identity": ("apps/tenant/portals/tests/test_portal_features.py", "StudentIdCardSelfViewTests"),
    "Students campus scope": ("apps/tenant/students/tests.py", "StudentCampusScopeTests"),
    "Parents campus scope": ("apps/tenant/parents/tests/test_parent_digest.py", "campus_admin_parent_registry_hides_other_campus_parent"),
    "HR campus scope": ("apps/tenant/hr/tests.py", "HrAdminCampusScopeTests"),
    "Payroll campus scope": ("apps/tenant/hr/tests.py", "PayrollCampusScopeTests"),
    "Analytics campus scope": ("apps/tenant/analytics/tests.py", "Hidden campus incident"),
    "Reports campus scope": ("apps/tenant/reports/tests.py", "ReportsCampusScopeTests"),
    "Library campus scope": ("apps/tenant/library/tests.py", "LibraryAdminCampusScopeTests"),
    "Hostels campus scope": ("apps/tenant/hostels/tests.py", "HostelAllocationCampusScopeTests"),
    "Transport campus scope": ("apps/tenant/transport/tests.py", "TransportAssignmentCampusScopeTests"),
    "Teachers campus scope": ("apps/tenant/teachers/tests.py", "TeacherCampusScopeTests"),
    "Coursework self-service scope": ("apps/tenant/coursework/tests.py", "test_student_cannot_force_browse_other_coursework_items"),
    "Tenant status isolation": ("apps/public/tenants/tests.py", "TenantStatusMiddlewareTests"),
    "Role continuity and principal access": ("apps/tenant/portals/test_role_continuity_hardening.py", "RoleContinuityHardeningTests"),
    "Privacy and 2FA continuity": ("apps/tenant/audit/test_account_gate_continuity.py", "AccountGateContinuityTests"),
    "Payslip role continuity": ("apps/tenant/hr/test_staff_payslip_continuity.py", "StaffPayslipContinuityTests"),
    "Quiz role and campus scope": ("apps/tenant/quizzes/test_role_and_campus_hardening.py", "QuizRoleAndCampusHardeningTests"),
    "Poll role and campus scope": ("apps/tenant/polls/test_portal_and_campus_hardening.py", "PollPortalAndCampusHardeningTests"),
}


class Command(BaseCommand):
    help = "Verify access-control and tenant-isolation implementation evidence."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        parser.add_argument("--strict", action="store_true", help="Fail when any evidence check is missing.")

    def handle(self, *args, **options):
        checks = self._checks()
        summary = {"ok": all(item["status"] == "pass" for item in checks), "checks": checks}

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2))
        else:
            self.stdout.write("Access-control evidence checklist")
            self.stdout.write("=" * 34)
            for item in checks:
                self.stdout.write(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")

        if options["strict"] and not summary["ok"]:
            failing = ", ".join(item["name"] for item in checks if item["status"] != "pass")
            raise CommandError(f"Access-control evidence check failed: {failing}")

    def _checks(self):
        root = Path(settings.BASE_DIR)
        permissions = self._read_text(root / "apps" / "tenant" / "portals" / "permissions.py")
        role_navigation = self._read_text(root / "apps" / "tenant" / "portals" / "role_navigation.py")
        campus_permissions = self._read_text(root / "apps" / "tenant" / "portals" / "campus_permissions.py")
        onboarding = self._read_text(root / "apps" / "public" / "tenants" / "onboarding.py")
        deployment_readiness = self._read_text(root / "apps" / "public" / "tenants" / "deployment_readiness.py")

        admin_role_contract = all(
            evidence in role_navigation
            for evidence in (
                "ADMIN_PORTAL_ROLE_CODES",
                "Role.ADMIN",
                "Role.CAMPUS_ADMIN",
                "Role.PRINCIPAL",
            )
        ) and "admin_portal_required = roles_required(*ADMIN_PORTAL_ROLE_CODES)" in permissions

        checks = [
            self._check(
                "Role gate primitive",
                "role_required" in permissions and "roles_required" in permissions,
                "permissions.py exposes role_required/roles_required",
            ),
            self._check(
                "Admin portal role contract",
                admin_role_contract,
                "central role_navigation contract includes admin, campus-admin and principal roles",
            ),
            self._check(
                "Campus scope helpers",
                "enforce_campus_scope" in campus_permissions and "validate_campus_access" in campus_permissions,
                "campus_permissions.py filters and validates campus access",
            ),
            self._check(
                "Tenant schema context",
                "tenant_context" in onboarding and 'connection.vendor == "postgresql"' in onboarding,
                "onboarding writes into tenant_context under PostgreSQL",
            ),
            self._check(
                "PostgreSQL tenant readiness",
                "Production tenant schemas require PostgreSQL" in deployment_readiness,
                "deployment readiness blocks real tenant schema claims on non-PostgreSQL",
            ),
        ]
        for name, (relative_path, evidence) in REQUIRED_TEST_EVIDENCE.items():
            text = self._read_text(root / relative_path)
            checks.append(self._check(name, evidence in text, f"{relative_path}: {evidence}"))
        return checks

    def _read_text(self, path):
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _check(self, name, ok, detail):
        return {"name": name, "status": "pass" if ok else "fail", "detail": detail}
