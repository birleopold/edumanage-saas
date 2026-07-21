from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...external_services import external_exam_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 6 external-examination readiness audit for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when external-exam configuration is incomplete.",
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
                readiness = external_exam_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Boards: {readiness['board_count']}; centres: {readiness['centre_count']}; "
                    f"sessions: {readiness['session_count']}; subjects: {readiness['subject_count']}; "
                    f"candidates: {readiness['candidate_count']}; results: {readiness['result_count']}; "
                    f"invalid records: {readiness['invalid_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 6 external examination configuration is ready."))
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 6 needs attention. No internal exams, marks, enrollments or learner records were changed."
                        )
                    )

        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"External examination audit found {incomplete} incomplete tenant(s).")
