from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...workflow_services import coursework_workflow_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 3 detailed activity and submission workflow audit."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when Phase 3 workflows are incomplete.",
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
                readiness = coursework_workflow_readiness()
                self.stdout.write(
                    self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}")
                )
                self.stdout.write(
                    f"Activities: {readiness['activity_count']}; submissions: {readiness['submission_count']}; "
                    f"missing profiles: {readiness['missing_profile_count']}; "
                    f"missing workflows: {readiness['missing_workflow_count']}."
                )
                self.stdout.write(
                    f"Invalid profiles: {readiness['invalid_profile_count']}; "
                    f"invalid workflows: {readiness['invalid_workflow_count']}; "
                    f"invalid groups: {readiness['invalid_group_count']}; "
                    f"over-capacity groups: {readiness['over_capacity_group_count']}; "
                    f"duplicate active memberships: {readiness['duplicate_active_membership_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(
                        self.style.SUCCESS("Phase 3 coursework workflows are ready.")
                    )
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 3 needs attention. Existing assignments and submissions were not deleted or replaced."
                        )
                    )
        self.stdout.write(
            f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed."
        )
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(
                f"Coursework workflow audit found {incomplete} incomplete tenant(s)."
            )
