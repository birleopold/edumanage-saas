from django.core.management.base import BaseCommand

from apps.tenant.finance import services as finance_services


class Command(BaseCommand):
    help = "Process due outbound webhook retry queue items."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        summary = finance_services.process_webhook_retry_queue(
            limit=options["limit"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "processed={processed} sent={sent} failed={failed} deactivated={deactivated} dry_run={dry}".format(
                    processed=summary.get("processed", 0),
                    sent=summary.get("sent", 0),
                    failed=summary.get("failed", 0),
                    deactivated=summary.get("deactivated", 0),
                    dry=summary.get("dry_run"),
                )
            )
        )
