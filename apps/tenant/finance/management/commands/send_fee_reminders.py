"""
Bulk fee reminder SMS (or log-only) for invoices with a positive balance.

Examples:
    python manage.py send_fee_reminders --overdue --dry-run
    python manage.py send_fee_reminders --invoice-id=42
    python manage.py send_fee_reminders --schema=tenant1 --overdue
"""
from django.core.management.base import BaseCommand

from apps.tenant.finance import services as finance_services
from apps.tenant.finance.models import Invoice
from apps.tenant.orgsettings.services import get_or_create_organization


class Command(BaseCommand):
    help = (
        "Send fee reminder messages for invoices "
        "(uses FEE_REMINDER_HANDLER / legacy FEE_REMINDER_SMS_HANDLER, or logs only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="",
            help="Tenant schema_name (PostgreSQL multi-tenant). If omitted, runs on the current DB schema only.",
        )
        parser.add_argument(
            "--invoice-id",
            type=int,
            default=None,
            help="Process a single invoice by primary key.",
        )
        parser.add_argument(
            "--overdue",
            action="store_true",
            help="Only active invoices past due date with positive balance (same rules as admin overdue list).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Maximum invoices to scan (default 200).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build messages but do not call SMS handler / log send.",
        )

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        if schema:
            from django_tenants.utils import schema_context

            from apps.public.tenants.models import Tenant

            tenants = list(Tenant.objects.exclude(schema_name="public").filter(schema_name=schema))
            if not tenants:
                self.stderr.write(self.style.ERROR(f"No tenant found with schema_name={schema!r}"))
                return
            for t in tenants:
                self.stdout.write(f"--- schema={t.schema_name} ---")
                with schema_context(t.schema_name):
                    self._run_for_tenant(options)
            return

        self._run_for_tenant(options)

    def _run_for_tenant(self, options):
        org = get_or_create_organization()
        currency = getattr(org, "default_currency", None) or "UGX"
        dry = options["dry_run"]
        limit = max(1, min(options["limit"], 2000))

        if options["invoice_id"]:
            qs = Invoice.objects.filter(pk=options["invoice_id"]).select_related("student")
        else:
            base = Invoice.objects.filter(status=Invoice.ACTIVE).select_related(
                "student", "academic_year", "academic_term"
            )
            if options["overdue"]:
                qs = finance_services.filter_invoices_overdue(base).order_by("due_date", "pk")
            else:
                qs = base.order_by("due_date", "pk")

        count = 0
        for inv in qs[:limit]:
            if inv.balance() <= 0:
                continue
            count += 1
            results = finance_services.send_fee_reminder_for_invoice(
                inv,
                currency_code=currency,
                school_name=org.name,
                dry_run=dry,
            )
            self.stdout.write(
                f"Invoice {inv.pk} student={inv.student_id} -> {results!r}"
            )

        if count == 0:
            self.stdout.write(self.style.WARNING("No invoices with positive balance matched."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Processed {count} invoice(s)."))
