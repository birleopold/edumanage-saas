from decimal import Decimal

import django.core.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0014_clearance_lifecycle_completion"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="clearancepermitsnapshot",
            old_name="finance_cle_access__bde5cf_idx",
            new_name="finance_cle_access__4e0702_idx",
        ),
        migrations.AlterField(
            model_name="clearanceoverride",
            name="approved_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="clearancepermitsnapshot",
            name="valid_from",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="clearancepolicy",
            name="minimum_paid_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                ],
            ),
        ),
    ]
