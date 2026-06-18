from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_accounting_layer")]

    operations = [
        migrations.CreateModel(
            name="BankStatementLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_date", models.DateField()),
                ("description", models.CharField(blank=True, max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("is_reconciled", models.BooleanField(default=False)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("cash_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="statement_lines", to="finance.cashaccount")),
                ("matched_payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="statement_matches", to="finance.payment")),
            ],
            options={"ordering": ("-transaction_date", "-id")},
        ),
    ]
