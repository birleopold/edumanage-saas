from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="opening_balance",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="Arrears or balance brought forward from a prior period (added to line totals).",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="mobile_network",
            field=models.CharField(
                blank=True,
                choices=[
                    ("MTN_MOMO", "MTN MoMo"),
                    ("AIRTEL_MONEY", "Airtel Money"),
                    ("OTHER", "Other mobile wallet"),
                ],
                help_text="When method is mobile money, optional network for reconciliation.",
                max_length=16,
            ),
        ),
    ]
