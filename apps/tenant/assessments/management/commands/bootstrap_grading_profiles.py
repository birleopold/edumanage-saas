from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...grading_services import bootstrap_default_grading_profile


class Command(BaseCommand):
    help = "Create a safe default Phase 4 grading profile from each tenant's active default grading scale."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for one tenant schema only.")
        parser.add_argument("--dry-run", action="store_true", help="Report intended changes without writing data.")

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        dry_run = bool(options.get("dry_run"))
        for tenant in tenants:
            with tenant_context(tenant):
                summary = bootstrap_default_grading_profile(dry_run=dry_run)
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    "Default scale available: "
                    f"{'yes' if summary['scale_available'] else 'no'}; "
                    f"profiles to create: {summary['profile_created']}; "
                    f"existing: {summary['profile_existing']}; "
                    f"report rules to create: {summary['rule_created']}."
                )
                if not summary["scale_available"]:
                    self.stdout.write(
                        self.style.WARNING(
                            "No active default grading scale is available. No grading profile was created."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Dry run complete; no data changed."
                            if dry_run
                            else "Grading profile bootstrap complete. Existing scales, marks and grades were not changed."
                        )
                    )
