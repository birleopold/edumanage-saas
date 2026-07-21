from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...activity_services import learning_activity_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 3 learning-activity audit for one or all school tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when Phase 3 links are incomplete.",
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
                readiness = learning_activity_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Activities: {readiness['activity_count']}; materials: {readiness['material_count']}; "
                    f"assignments: {readiness['assignment_count']}; missing source links: {readiness['missing_source_count']}."
                )
                self.stdout.write(
                    f"Unlinked submissions: {readiness['unlinked_submission_count']}; "
                    f"comments: {readiness['unlinked_comment_count']}; progress: {readiness['unlinked_progress_count']}; "
                    f"stale snapshots: {readiness['stale_snapshot_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 3 learning activities are structurally ready."))
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Phase 3 needs attention: {readiness['issue_count']} issue(s). No data was changed."
                        )
                    )
        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Learning-activity audit found {incomplete} incomplete tenant(s).")
