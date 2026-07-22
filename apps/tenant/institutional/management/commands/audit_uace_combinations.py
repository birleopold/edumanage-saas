from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...uace_services import uace_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 5 UACE subject-role and capacity audit."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when UACE combination configuration is incomplete.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")

        incomplete = 0
        audited = 0
        for tenant in tenants:
            audited += 1
            with tenant_context(tenant):
                readiness = uace_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Policies: {readiness['combination_policy_count']}; "
                    f"invalid combinations: {readiness['invalid_combination_count']}; "
                    f"registrations without policy: {readiness['registration_without_policy_count']}; "
                    f"over-capacity registrations: {readiness['over_capacity_registration_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 5 UACE configuration is ready."))
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 5 needs attention. Existing combinations and learner registrations were not changed."
                        )
                    )
        self.stdout.write(
            f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed."
        )
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"UACE audit found {incomplete} incomplete tenant(s).")
