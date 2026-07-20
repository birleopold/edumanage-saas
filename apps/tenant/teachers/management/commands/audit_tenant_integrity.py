from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant
from apps.tenant.orgsettings.integrity import audit_current_tenant, summarize_issues


class Command(BaseCommand):
    help = "Run a read-only cross-module data integrity audit for one or all school tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            help="Audit one tenant schema only, for example demo.",
        )
        parser.add_argument(
            "--fail-on-errors",
            action="store_true",
            help="Return a non-zero exit code when ERROR findings exist.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        fail_on_errors = bool(options.get("fail_on_errors"))

        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")

        total_errors = 0
        total_warnings = 0
        audited = 0

        for tenant in tenants:
            audited += 1
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))

            with tenant_context(tenant):
                issues = audit_current_tenant()

            if not issues:
                self.stdout.write(self.style.SUCCESS("No integrity conflicts found."))
                continue

            summary = summarize_issues(issues)
            total_errors += summary.get("ERROR", 0)
            total_warnings += summary.get("WARNING", 0)

            for issue in issues:
                prefix = self.style.ERROR("ERROR") if issue.severity == "ERROR" else self.style.WARNING("WARNING")
                self.stdout.write(f"[{prefix}] {issue.code}: {issue.message} Affected: {issue.count}.")
                for sample in issue.samples:
                    self.stdout.write(f"    - {sample}")

            self.stdout.write(
                f"Tenant summary: {summary.get('ERROR', 0)} error type(s), "
                f"{summary.get('WARNING', 0)} warning type(s)."
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Audit complete: {audited} tenant(s), {total_errors} error type(s), "
                f"{total_warnings} warning type(s). No data was changed."
            )
        )

        if fail_on_errors and total_errors:
            raise CommandError(f"Integrity audit found {total_errors} error type(s).")
