from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tenant.inventory.models import InventoryItem


class Command(BaseCommand):
    help = "Compare cached inventory balances with the immutable movement ledger."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Replace mismatched cached balances.")

    def handle(self, *args, **options):
        mismatches = []
        with transaction.atomic():
            items = InventoryItem.objects.select_for_update().order_by("pk")
            for item in items.iterator():
                ledger_balance = item.ledger_stock_on_hand()
                if item.cached_stock_on_hand != ledger_balance:
                    mismatches.append((item, ledger_balance))
                    self.stdout.write(
                        f"MISMATCH item={item.pk} cached={item.cached_stock_on_hand} ledger={ledger_balance}"
                    )
                    if options["fix"]:
                        InventoryItem.objects.filter(pk=item.pk).update(
                            cached_stock_on_hand=ledger_balance
                        )

        if mismatches and not options["fix"]:
            raise CommandError(f"Found {len(mismatches)} inventory balance mismatch(es).")
        action = "repaired" if options["fix"] else "verified"
        self.stdout.write(self.style.SUCCESS(f"Inventory balances {action}; mismatches={len(mismatches)}"))
