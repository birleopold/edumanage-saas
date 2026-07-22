from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...policy_services import assessment_policy_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 2 assessment and result-policy audit."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when Phase 2 policies are incomplete.",
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
                readiness = assessment_policy_readiness()
                self.stdout.write(
                    self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}")
                )
                self.stdout.write(
                    f"Assessments: {readiness['assessment_count']}; "
                    f"scores: {readiness['score_count']}; "
                    f"missing assessment policies: {readiness['missing_assessment_policy_count']}; "
                    f"missing score policies: {readiness['missing_score_policy_count']}."
                )
                self.stdout.write(
                    f"Invalid assessment policies: {readiness['invalid_assessment_policy_count']}; "
                    f"invalid score policies: {readiness['invalid_score_policy_count']}; "
                    f"competency ratings missing: {readiness['competency_without_rating_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(
                        self.style.SUCCESS("Phase 2 assessment policies are ready.")
                    )
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 2 needs attention. Existing marks were not changed."
                        )
                    )
        self.stdout.write(
            f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed."
        )
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(
                f"Assessment-policy audit found {incomplete} incomplete tenant(s)."
            )
