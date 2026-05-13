from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.tenant.finance import services as finance_services
from apps.tenant.orgsettings.services import get_or_create_organization


class Command(BaseCommand):
    help = "Send attendance absence alerts to opted-in parents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="",
            help="Attendance date in YYYY-MM-DD (defaults to today).",
        )
        parser.add_argument(
            "--campus-id",
            type=int,
            default=None,
            help="Optional campus filter.",
        )
        parser.add_argument(
            "--include-late",
            action="store_true",
            help="Include LATE attendance entries as alerts.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Create DRY_RUN logs without sending provider requests.",
        )

    def handle(self, *args, **options):
        target_date = (options.get("date") or "").strip() or timezone.localdate().isoformat()
        org = get_or_create_organization()
        summary = finance_services.send_absence_alerts_for_date(
            target_date,
            campus_id=options.get("campus_id"),
            include_late=bool(options.get("include_late")),
            school_name=org.name,
            dry_run=bool(options.get("dry_run")),
        )
        self.stdout.write(
            "date={date} entries={entries} sent={sent} failed={failed} no_phone={no_phone} dry_run={dry}".format(
                date=target_date,
                entries=summary["entries"],
                sent=summary["sent"],
                failed=summary["failed"],
                no_phone=summary["no_phone"],
                dry=summary["dry_run_count"],
            )
        )
