from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...grading_services import grading_framework_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 4 grading-profile and report-rule audit for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when Phase 4 configuration is incomplete.",
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
                readiness = grading_framework_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Profiles: {readiness['profile_count']}; "
                    f"active: {readiness['active_profile_count']}; "
                    f"invalid: {readiness['invalid_profile_count']}; "
                    f"missing report rules: {readiness['missing_report_rule_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 4 grading framework is structurally ready."))
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 4 needs attention. No grading scales, score records or historical grades were changed."
                        )
                    )
        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Grading framework audit found {incomplete} incomplete tenant(s).")
