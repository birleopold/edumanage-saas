from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.tenant.audit.models import AuditEvent, DataRetentionPolicy, LoginHistory


class Command(BaseCommand):
    help = "Scan audit records against configured retention rules."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        model_map = {"audit": AuditEvent, "login": LoginHistory}
        total = 0
        for rule in DataRetentionPolicy.objects.filter(is_active=True):
            model = model_map.get(rule.module)
            if not model:
                continue
            cutoff = timezone.now() - timezone.timedelta(days=rule.retention_days)
            count = model.objects.filter(created_at__lt=cutoff).count()
            total += count
            self.stdout.write(f"{rule.module}: {count} old records")
        self.stdout.write(self.style.SUCCESS(f"Retention scan complete: {total}"))
