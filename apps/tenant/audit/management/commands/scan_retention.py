from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.tenant.audit.models import AuditEvent, DataRetentionPolicy, LoginHistory


class Command(BaseCommand):
    help = "Scan and optionally enforce supported audit-data retention rules."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report eligible rows without changing data.")
        parser.add_argument("--apply", action="store_true", help="Apply DELETE retention actions. Must be explicitly supplied.")
        parser.add_argument("--limit", type=int, default=5000, help="Maximum rows deleted per rule per run.")

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Use either --apply or --dry-run, not both.")
        apply_changes = bool(options["apply"])
        limit = max(1, min(int(options["limit"] or 5000), 50000))
        model_map = {"audit": AuditEvent, "login": LoginHistory}
        total_eligible = total_deleted = 0

        for rule in DataRetentionPolicy.objects.filter(is_active=True):
            model = model_map.get(rule.module)
            if not model:
                self.stdout.write(self.style.WARNING(f"{rule.module}: unsupported module; no action taken"))
                continue
            cutoff = timezone.now() - timezone.timedelta(days=rule.retention_days)
            qs = model.objects.filter(created_at__lt=cutoff).order_by("pk")
            eligible = qs.count()
            total_eligible += eligible
            action = (rule.action_after_retention or "ARCHIVE").strip().upper()

            if not apply_changes:
                self.stdout.write(f"{rule.module}: {eligible} eligible; action={action}; dry-run")
                continue

            if action != "DELETE":
                self.stdout.write(self.style.WARNING(f"{rule.module}: {eligible} eligible; action={action} is non-destructive and requires an archive backend; no rows changed"))
                continue

            ids = list(qs.values_list("pk", flat=True)[:limit])
            if not ids:
                self.stdout.write(f"{rule.module}: 0 deleted")
                continue
            with transaction.atomic():
                deleted, _ = model.objects.filter(pk__in=ids, created_at__lt=cutoff).delete()
            total_deleted += deleted
            self.stdout.write(self.style.SUCCESS(f"{rule.module}: deleted {deleted} rows (batch limit {limit})"))

        self.stdout.write(self.style.SUCCESS(f"Retention scan complete: eligible={total_eligible} deleted={total_deleted} apply={apply_changes}"))
