"""
Carry positive balances from all invoices in one academic term into another.

  python manage.py carry_invoice_balances --source-term=3 --target-year=1 --target-term=4 --dry-run
  python manage.py carry_invoice_balances --schema=tenant1 --source-term=3 --target-year=1 --target-term=4
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenant.finance import services as finance_services


class Command(BaseCommand):
    help = "Bulk carry-forward invoice balances from one term to another."

    def add_arguments(self, parser):
        parser.add_argument("--source-term", type=int, required=True, dest="source_term")
        parser.add_argument("--target-year", type=int, required=True, dest="target_year")
        parser.add_argument("--target-term", type=int, required=True, dest="target_term")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--schema",
            type=str,
            default="",
            help="Tenant schema_name (django-tenants). If set, runs inside that schema.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        if schema:
            from django_tenants.utils import schema_context

            from apps.public.tenants.models import Tenant

            tenants = list(
                Tenant.objects.exclude(schema_name="public").filter(schema_name=schema)
            )
            if not tenants:
                raise CommandError(f"No tenant with schema_name={schema!r}")
            for t in tenants:
                self.stdout.write(f"--- schema={t.schema_name} ---")
                with schema_context(t.schema_name):
                    self._run(options)
            return

        self._run(options)

    def _run(self, options):
        try:
            summary = finance_services.bulk_carry_balances_for_term(
                source_term_id=options["source_term"],
                target_year_id=options["target_year"],
                target_term_id=options["target_term"],
                dry_run=options["dry_run"],
            )
        except Exception as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(str(summary)))
        for err in summary.get("errors") or []:
            self.stdout.write(self.style.WARNING(f"Invoice {err.get('invoice_id')}: {err.get('error')}"))
