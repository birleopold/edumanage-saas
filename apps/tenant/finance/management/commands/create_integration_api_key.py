from django.core.management.base import BaseCommand

from apps.tenant.finance.models import IntegrationApiKey


class Command(BaseCommand):
    help = "Create integration API key for Phase 3 endpoints."

    def add_arguments(self, parser):
        parser.add_argument("--name", type=str, default="Default Integration Key", help="Display name for the key.")

    def handle(self, *args, **options):
        obj, raw_key = IntegrationApiKey.create_with_plaintext(options["name"])
        self.stdout.write(self.style.SUCCESS(f"Created key id={obj.pk} name={obj.name}"))
        self.stdout.write(self.style.WARNING("Store this API key securely; it will not be shown again:"))
        self.stdout.write(raw_key)
