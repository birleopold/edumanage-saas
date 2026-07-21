from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...clearance_services import clearance_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 9 fee-clearance readiness audit for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when invalid policy structure is found.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        audited = 0
        incomplete = 0
        for tenant in tenants:
            audited += 1
            with tenant_context(tenant):
                readiness = clearance_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Policies: {readiness['policy_count']} total, {readiness['active_policy_count']} active, "
                    f"{readiness['invalid_policy_count']} invalid; overrides: {readiness['override_count']}; "
                    f"expired but active overrides: {readiness['expired_active_override_count']}; "
                    f"decision logs: {readiness['decision_log_count']}."
                )
                if readiness["missing_access_types"]:
                    self.stdout.write(
                        "Unconfigured access types (remain open): " + ", ".join(readiness["missing_access_types"])
                    )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 9 clearance structure is valid."))
                else:
                    incomplete += 1
                    self.stdout.write(self.style.WARNING("Invalid clearance policies need attention. No data was changed."))
        self.stdout.write(
            f"Audit complete: {audited} tenant(s), {incomplete} structurally incomplete. No invoice, payment, score or access record was changed."
        )
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Clearance audit found {incomplete} incomplete tenant(s).")
