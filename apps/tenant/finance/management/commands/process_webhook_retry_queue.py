from django.core.management.base import BaseCommand

from apps.tenant.finance import services as finance_services


class Command(BaseCommand):
    help = "Process due outbound webhook retry queue items."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Maximum retry items to process.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report due items without sending webhook requests.",
        )

    def handle(self, *args, **options):
        summary = finance_services.process_webhook_retry_queue(
            limit=max(1, min(int(options["limit"]), 1000)),
            dry_run=bool(options.get("dry_run")),
        )
        self.stdout.write(
            "processed={processed} sent={sent} failed={failed} deactivated={deactivated} dry_run={dry_run}".format(
                **summary
            )
        )
