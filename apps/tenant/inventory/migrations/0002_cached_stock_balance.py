from decimal import Decimal

from django.db import migrations, models
from django.db.models import Sum


def populate_cached_balances(apps, schema_editor):
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    StockMovement = apps.get_model("inventory", "StockMovement")
    for item in InventoryItem.objects.all().iterator():
        totals = StockMovement.objects.filter(item_id=item.pk).aggregate(
            in_qty=Sum("quantity", filter=models.Q(movement_type="IN")),
            out_qty=Sum("quantity", filter=models.Q(movement_type="OUT")),
            adj_qty=Sum("quantity", filter=models.Q(movement_type="ADJUST")),
        )
        balance = (
            (totals["in_qty"] or Decimal("0"))
            - (totals["out_qty"] or Decimal("0"))
            + (totals["adj_qty"] or Decimal("0"))
        )
        InventoryItem.objects.filter(pk=item.pk).update(cached_stock_on_hand=balance)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="cached_stock_on_hand",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.RunPython(populate_cached_balances, migrations.RunPython.noop),
    ]
