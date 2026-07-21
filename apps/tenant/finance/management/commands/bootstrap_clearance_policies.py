from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from apps.public.tenants.models import Tenant

from ...clearance_services import bootstrap_policy_templates


class Command(BaseCommand):
    help = "Create inactive Phase 9 clearance-policy templates for one or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Process one tenant schema only.")
        parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")

    def handle(self, *args, **options):
        schema = (options.get("schema") or "").strip()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")
        if schema:
            tenants = tenants.filter(schema_name=schema)
            if not tenants.exists():
                raise CommandError(f"Tenant schema '{schema}' was not found.")
        apply = bool(options.get("apply"))
        processed = 0
        for tenant in tenants:
            processed += 1
            with tenant_context(tenant):
                rows = bootstrap_policy_templates(apply=apply)
                missing = sum(1 for row in rows if not row["exists"])
                self.stdout.write(self.style.MIGRATE_HEADING(f"Tenant: {tenant.schema_name}"))
                self.stdout.write(f"Templates: {len(rows)}; missing before run: {missing}.")
                if apply:
                    self.stdout.write(self.style.SUCCESS("Inactive Phase 9 policy templates created safely."))
                else:
                    self.stdout.write(self.style.WARNING("Dry run only. Re-run with --apply to create templates."))
        self.stdout.write(
            f"Bootstrap complete: {processed} tenant(s). Templates are inactive; no invoice, payment, score, attempt or learner record was changed."
        )
