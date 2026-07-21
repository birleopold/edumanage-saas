from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...hardening_services import phase7_operational_readiness
from ...welfare_services import boarding_welfare_readiness


class Command(BaseCommand):
    help = "Run a read-only Phase 7 boarding and welfare readiness audit for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Audit one tenant schema only.")
        parser.add_argument(
            "--fail-on-incomplete",
            action="store_true",
            help="Return a non-zero exit code when structural or operational Phase 7 readiness is incomplete.",
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
                readiness = boarding_welfare_readiness()
                operations = phase7_operational_readiness()
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(
                    f"Profiles: {readiness['profile_count']}/{readiness['active_student_count']}; "
                    f"active allocations: {readiness['active_allocation_count']}; "
                    f"boarders without allocation: {readiness['boarder_without_allocation_count']}; "
                    f"allocations without boarder profile: {readiness['allocation_without_boarder_profile_count']}; "
                    f"completed roll calls with unmarked learners: {readiness['completed_roll_call_with_unmarked_count']}."
                )
                self.stdout.write(
                    f"Operational alerts: overdue leave {readiness['overdue_leave_count']}; "
                    f"open welfare cases {readiness['open_case_count']}; "
                    f"unresolved critical cases {readiness['unresolved_critical_case_count']}; "
                    f"boarders missing guardian contacts {operations['boarder_missing_guardian_contact_count']}; "
                    f"departures without confirmation {operations['departed_without_confirmation_count']}; "
                    f"overdue case responses {operations['overdue_case_response_count']}; "
                    f"unassigned high-priority cases {operations['unassigned_high_priority_case_count']}; "
                    f"draft roll calls needing reconciliation {operations['draft_roll_call_mismatch_count']}."
                )
                if readiness["ready"] and operations["ready"]:
                    self.stdout.write(self.style.SUCCESS("Phase 7 boarding and welfare structure and operations are ready."))
                else:
                    incomplete += 1
                    self.stdout.write(
                        self.style.WARNING(
                            "Phase 7 needs attention. No bed allocations, learner placement, sickbay, discipline or finance records were changed."
                        )
                    )
        self.stdout.write(f"Audit complete: {audited} tenant(s), {incomplete} incomplete. No data was changed.")
        if options.get("fail_on_incomplete") and incomplete:
            raise CommandError(f"Boarding and welfare audit found {incomplete} incomplete tenant(s).")
