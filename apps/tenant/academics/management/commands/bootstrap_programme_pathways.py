from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...pathway_services import bootstrap_programme_pathways


class Command(BaseCommand):
    help = "Create additive Phase 5 programme pathways and subject combinations from existing programme/course links."

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
                summary = bootstrap_programme_pathways(dry_run=dry_run)
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Pathways to create: {summary['pathways_created']}; "
                    f"existing: {summary['pathways_existing']}; "
                    f"level links: {summary['levels_created']}; "
                    f"combinations to create: {summary['combinations_created']}; "
                    f"existing combinations: {summary['combinations_existing']}; "
                    f"course links: {summary['courses_linked']}."
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        "Dry run complete; no data changed."
                        if dry_run
                        else "Bootstrap complete. Existing programmes, courses, classes, students, offerings and enrollments were not changed."
                    )
                )
