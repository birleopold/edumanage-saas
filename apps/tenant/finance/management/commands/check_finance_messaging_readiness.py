from django.core.management.base import BaseCommand

from apps.tenant.finance import services as finance_services


class Command(BaseCommand):
    help = "Print quick readiness snapshot for fee/receipt messaging."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-limit",
            type=int,
            default=50,
            help="How many invoices to sample for readiness checks (default 50).",
        )

    def handle(self, *args, **options):
        snapshot = finance_services.messaging_readiness_snapshot(
            sample_limit=max(1, min(options["sample_limit"], 500))
        )
        for key in (
            "channel",
            "handler_configured",
            "handler_resolved",
            "portal_base_configured",
            "whatsapp_token_set",
            "whatsapp_phone_number_id_set",
            "invoice_sample_size",
            "outstanding_invoices_in_sample",
            "outstanding_with_parent_phone_in_sample",
            "failed_logs_count",
        ):
            self.stdout.write(f"{key}={snapshot.get(key)}")
