from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...welfare_services import bootstrap_boarding_profiles


class Command(BaseCommand):
    help = "Preview or explicitly create Phase 7 boarding profiles from existing active learner and bed-allocation records."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for one tenant schema only.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create missing profiles. Without this flag the command is a dry run.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        apply_changes = bool(options.get("apply"))
        for tenant in tenants:
            with tenant_context(tenant):
                summary = bootstrap_boarding_profiles(dry_run=not apply_changes)
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Active learners: {summary['student_count']}; existing profiles: {summary['existing_count']}; "
                    f"profiles to create: {summary['created_count']} "
                    f"({summary['boarder_profile_count']} boarder, {summary['day_profile_count']} day)."
                )
                if apply_changes:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Boarding profile bootstrap complete. Bed allocations, learner placement, health, discipline and finance records were not changed."
                        )
                    )
                else:
                    self.stdout.write(self.style.SUCCESS("Dry run complete; no data changed. Add --apply to create profiles."))
