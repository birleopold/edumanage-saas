from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...programme_services import bootstrap_activity_programmes


class Command(BaseCommand):
    help = "Create additive Phase 8 programme and participation profiles for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Process one tenant schema only.")
        parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        dry_run = not options.get("apply")
        processed = 0
        for tenant in tenants:
            processed += 1
            with tenant_context(tenant):
                summary = bootstrap_activity_programmes(dry_run=dry_run)
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Activities: {summary['activity_count']}; programme profiles to create: "
                    f"{summary['programme_created_count']}; memberships: {summary['membership_count']}; "
                    f"participation profiles to create: {summary['participation_created_count']}."
                )
                if dry_run:
                    self.stdout.write(self.style.WARNING("Dry run only. Re-run with --apply to create records."))
                else:
                    self.stdout.write(self.style.SUCCESS("Phase 8 profiles created safely."))
        self.stdout.write(f"Bootstrap complete: {processed} tenant(s). No activities, memberships, learners or finance records were changed.")
