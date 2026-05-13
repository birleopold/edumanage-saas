from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.tenant.reports.models import ReportRun
from apps.tenant.reports.scheduler import execute_overview_csv_run


class Command(BaseCommand):
    help = (
        "Generate operational overview CSV reports (last 30 days, all campuses). "
        "Schedule with cron or Windows Task Scheduler against your venv Python."
    )

    def handle(self, *args, **options):
        end = timezone.localdate()
        start = end - timedelta(days=30)
        run = execute_overview_csv_run(triggered_by=None, start=start, end=end, campus_id=None)
        if run.status == ReportRun.STATUS_SUCCESS:
            self.stdout.write(self.style.SUCCESS(f"Report run #{run.pk} OK → {run.file_path}"))
        else:
            self.stderr.write(self.style.ERROR(run.detail or "Failed"))
