from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...programme_services import activity_programme_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 8 co-curricular readiness audit for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when structural readiness is incomplete.",
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
                readiness = activity_programme_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Programmes: {readiness['programme_count']}/{readiness['activity_count']}; "
                    f"participation profiles: {readiness['participation_count']}/{readiness['membership_count']}; "
                    f"over capacity: {readiness['over_capacity_count']}; completed sessions with unmarked attendance: "
                    f"{readiness['completed_session_with_unmarked_count']}."
                )
                self.stdout.write(
                    f"Operational alerts: consent missing {readiness['consent_missing_count']}; "
                    f"medical clearance missing {readiness['medical_clearance_missing_count']}; "
                    f"sessions {readiness['session_count']}."
                )
                if readiness["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 8 co-curricular structure is ready."))
                else:
                    incomplete += 1
                    self.stdout.write(self.style.WARNING("Phase 8 needs attention. No activity, membership, learner, staff or finance data was changed."))
        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Co-curricular audit found {incomplete} incomplete tenant(s).")
