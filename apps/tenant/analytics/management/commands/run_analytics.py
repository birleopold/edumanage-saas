from django.core.management.base import BaseCommand

from apps.tenant.academics.models import AcademicTerm
from apps.tenant.analytics.intelligence import run_analytics
from apps.tenant.analytics.intelligence_models import AnalyticsRun


class Command(BaseCommand):
    help = "Generate analytics snapshots, alerts, recommendations, comments, class reports, and teacher metrics."

    def add_arguments(self, parser):
        parser.add_argument("--term-id", type=int, default=None)
        parser.add_argument("--scheduled", action="store_true")

    def handle(self, *args, **options):
        term = None
        if options.get("term_id"):
            term = AcademicTerm.objects.get(pk=options["term_id"])
        run = run_analytics(term=term, run_type=AnalyticsRun.SCHEDULED if options.get("scheduled") else AnalyticsRun.MANUAL)
        self.stdout.write(self.style.SUCCESS(f"Analytics run {run.id}: snapshots={run.generated_snapshots}, alerts={run.generated_alerts}, classes={run.generated_class_reports}, teachers={run.generated_teacher_metrics}"))
