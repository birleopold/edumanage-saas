from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...models import HostelRollCall
from ...hardening_services import reconcile_roll_call_leave_statuses


class Command(BaseCommand):
    help = "Preview or apply safe leave-status reconciliation for draft hostel roll calls."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for one tenant schema only.")
        parser.add_argument("--roll-call", type=int, help="Limit reconciliation to one roll-call ID.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply safe changes. Without this flag the command is read-only.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        roll_call_id = options.get("roll_call")
        apply_changes = bool(options.get("apply"))
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")

        audited = 0
        total_roll_calls = 0
        total_changes = 0
        for tenant in tenants:
            audited += 1
            with tenant_context(tenant):
                roll_calls = HostelRollCall.objects.filter(status=HostelRollCall.DRAFT).order_by("pk")
                if roll_call_id:
                    roll_calls = roll_calls.filter(pk=roll_call_id)
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                tenant_roll_calls = 0
                tenant_changes = 0
                for roll_call in roll_calls:
                    summary = reconcile_roll_call_leave_statuses(
                        roll_call,
                        dry_run=not apply_changes,
                    )
                    tenant_roll_calls += 1
                    tenant_changes += summary["change_count"]
                    if summary["change_count"]:
                        self.stdout.write(
                            f"Roll call {roll_call.pk}: "
                            f"on leave {summary['set_on_leave_count']}; "
                            f"reset {summary['reset_to_unmarked_count']}; "
                            f"explicit decisions preserved {summary['preserved_explicit_count']}."
                        )
                total_roll_calls += tenant_roll_calls
                total_changes += tenant_changes
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Reviewed {tenant_roll_calls} draft roll call(s); "
                        f"{'applied' if apply_changes else 'previewed'} {tenant_changes} safe change(s)."
                    )
                )

        self.stdout.write(
            f"Reconciliation complete: {audited} tenant(s), {total_roll_calls} draft roll call(s), "
            f"{total_changes} safe change(s). "
            f"{'Changes applied.' if apply_changes else 'Dry run only; no data changed.'}"
        )
