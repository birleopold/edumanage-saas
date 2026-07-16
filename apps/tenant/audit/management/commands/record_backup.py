from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.tenant.audit.models import BackupJob


class Command(BaseCommand):
    help = "Record a backup/restore workflow event for audit tracking."

    def add_arguments(self, parser):
        parser.add_argument("--status", default=BackupJob.REQUESTED, choices=[choice[0] for choice in BackupJob.STATUS_CHOICES])
        parser.add_argument("--file-path", default="")
        parser.add_argument("--checksum", default="")
        parser.add_argument("--notes", default="")

    def handle(self, *args, **options):
        status = options["status"]
        if status not in {choice[0] for choice in BackupJob.STATUS_CHOICES}:
            raise CommandError(f"Unknown backup status: {status}")
        now = timezone.now()
        job = BackupJob.objects.create(status=status, file_path=options["file_path"], checksum=options["checksum"], notes=options["notes"], started_at=now if status in [BackupJob.RUNNING, BackupJob.SUCCESS, BackupJob.FAILED, BackupJob.RESTORE_TESTED] else None, finished_at=now if status in [BackupJob.SUCCESS, BackupJob.FAILED, BackupJob.RESTORE_TESTED] else None)
        self.stdout.write(self.style.SUCCESS(f"Backup audit record created: {job.id} ({job.status})"))
