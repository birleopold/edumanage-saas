from django.core.management.base import BaseCommand, CommandError

from apps.tenant.announcements.models import Announcement
from apps.tenant.finance import services as finance_services
from apps.tenant.orgsettings.services import get_or_create_organization


class Command(BaseCommand):
    help = "Broadcast one urgent announcement to opted-in parents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--announcement-id",
            type=int,
            required=True,
            help="Announcement primary key.",
        )
        parser.add_argument(
            "--campus-id",
            type=int,
            default=None,
            help="Optional campus filter.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Create DRY_RUN logs without sending provider requests.",
        )

    def handle(self, *args, **options):
        announcement_id = options["announcement_id"]
        ann = Announcement.objects.filter(pk=announcement_id).first()
        if not ann:
            raise CommandError(f"Announcement {announcement_id} not found.")
        if not ann.is_urgent:
            raise CommandError("Announcement is not marked urgent.")

        org = get_or_create_organization()
        summary = finance_services.send_urgent_announcement_broadcast(
            ann,
            campus_id=options.get("campus_id"),
            school_name=org.name,
            dry_run=bool(options.get("dry_run")),
        )
        if summary.get("skipped"):
            raise CommandError("Broadcast skipped due to unsupported audience. Use ALL or PARENTS.")
        self.stdout.write(
            "announcement={aid} sent={sent} failed={failed} no_phone={no_phone} dry_run={dry}".format(
                aid=announcement_id,
                sent=summary["sent"],
                failed=summary["failed"],
                no_phone=summary["no_phone"],
                dry=summary["dry_run_count"],
            )
        )
