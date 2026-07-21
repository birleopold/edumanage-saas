from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...activity_services import sync_all_learning_activities


class Command(BaseCommand):
    help = "Create additive Phase 3 learning-activity orchestration links for existing coursework records."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for one tenant schema only.")
        parser.add_argument(
            "--refresh-classification",
            action="store_true",
            help="Refresh generated kinds and default policies; administrator-edited policies are otherwise preserved.",
        )
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
                summary = sync_all_learning_activities(
                    dry_run=dry_run,
                    refresh_policy=bool(options.get("refresh_classification")),
                )
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                if dry_run:
                    self.stdout.write(
                        "To create: "
                        f"materials={summary['materials_to_create']}, "
                        f"assignments={summary['assignments_to_create']}; "
                        f"stale titles={summary['stale_titles']}; "
                        f"stale status={summary['stale_status']}; "
                        f"reclassification={summary['activities_to_reclassify']}; "
                        f"metadata links={summary['metadata_links_to_add']}."
                    )
                else:
                    self.stdout.write(
                        "Created: "
                        f"materials={summary['materials_created']}, "
                        f"assignments={summary['assignments_created']}; "
                        f"activities updated={summary['activities_updated']}; "
                        f"metadata links added={summary['metadata_links_added']}."
                    )
                self.stdout.write(
                    self.style.SUCCESS(
                        "Dry run complete; no data changed."
                        if dry_run
                        else "Learning-activity bootstrap complete. Existing coursework content, submissions, comments, scores and progress values were not changed."
                    )
                )
