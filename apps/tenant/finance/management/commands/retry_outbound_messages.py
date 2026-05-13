from django.core.management.base import BaseCommand

from apps.tenant.finance import services as finance_services


class Command(BaseCommand):
    help = "Retry outbound message logs (defaults to FAILED logs only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum logs to process (default 100).",
        )
        parser.add_argument(
            "--all-statuses",
            action="store_true",
            help="Retry logs regardless of status (default is FAILED only).",
        )
        parser.add_argument(
            "--message-type",
            type=str,
            default="",
            help="Filter by message type (FEE_REMINDER or PAYMENT_RECEIPT).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Create DRY_RUN retry logs without dispatching to provider.",
        )

    def handle(self, *args, **options):
        summary = finance_services.retry_outbound_message_logs(
            limit=max(1, min(options["limit"], 1000)),
            dry_run=bool(options["dry_run"]),
            only_failed=not bool(options["all_statuses"]),
            message_type=(options.get("message_type") or "").strip().upper(),
        )
        self.stdout.write(
            "processed={processed} sent={sent} failed={failed} skipped={skipped} dry_run={dry_run}".format(
                **summary
            )
        )
