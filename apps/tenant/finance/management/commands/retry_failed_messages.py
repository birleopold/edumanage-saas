from django.core.management.base import BaseCommand

from apps.tenant.finance import services as finance_services


class Command(BaseCommand):
    help = "Retry failed outbound SMS/WhatsApp message logs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--message-type", default="", help="Optional message type filter, e.g. FEE_REMINDER")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        summary = finance_services.retry_outbound_message_logs(
            limit=options["limit"],
            dry_run=options["dry_run"],
            only_failed=True,
            message_type=options["message_type"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "processed={processed} sent={sent} failed={failed} skipped={skipped} dry_run={dry}".format(
                    processed=summary.get("processed", 0),
                    sent=summary.get("sent", 0),
                    failed=summary.get("failed", 0),
                    skipped=summary.get("skipped", 0),
                    dry=summary.get("dry_run_count", 0),
                )
            )
        )
