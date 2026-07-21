from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...pathway_services import pathway_framework_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 5 programme-pathway and subject-combination audit."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when Phase 5 configuration is incomplete.",
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
                readiness = pathway_framework_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Pathways: {readiness['pathway_count']}; "
                    f"combinations: {readiness['combination_count']}; "
                    f"assignments: {readiness['assignment_count']}; "
                    f"unassigned programme class groups: {readiness['unassigned_class_group_count']}; "
                    f"invalid pathways: {readiness['invalid_pathway_count']}; "
                    f"invalid combinations: {readiness['invalid_combination_count']}; "
                    f"invalid assignments: {readiness['invalid_assignment_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 5 pathway framework is structurally ready."))
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 5 needs attention. Existing programmes, courses, classes, learners, offerings and enrollments were not changed."
                        )
                    )
        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Programme-pathway audit found {incomplete} incomplete tenant(s).")
