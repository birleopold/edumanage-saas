# Generated manually for full finance accounting layer

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_mobilepaymentrequest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("account_type", models.CharField(choices=[("ASSET", "Asset"), ("LIABILITY", "Liability"), ("EQUITY", "Equity"), ("INCOME", "Income"), ("EXPENSE", "Expense")], max_length=16)),
                ("is_control_account", models.BooleanField(default=False)),
                ("is_bank_or_cash", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="children", to="finance.account")),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="CashAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("kind", models.CharField(choices=[("CASH", "Cash"), ("BANK", "Bank"), ("MOBILE_MONEY", "Mobile money"), ("CARD", "Card/Card settlement")], max_length=20)),
                ("bank_name", models.CharField(blank=True, max_length=120)),
                ("account_number", models.CharField(blank=True, max_length=80)),
                ("mobile_network", models.CharField(blank=True, max_length=32)),
                ("opening_balance", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("ledger_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cash_accounts", to="finance.account")),
            ],
            options={"ordering": ("kind", "name")},
        ),
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("expense_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expense_categories", to="finance.account")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="SchoolExpense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expense_date", models.DateField(default=django.utils.timezone.localdate)),
                ("supplier", models.CharField(blank=True, max_length=160)),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("reference", models.CharField(blank=True, max_length=80)),
                ("is_posted", models.BooleanField(default=False)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="finance.expensecategory")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("paid_from", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="finance.cashaccount")),
            ],
            options={"ordering": ("-expense_date", "-id")},
        ),
        migrations.CreateModel(
            name="PayrollRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("APPROVED", "Approved"), ("PAID", "Paid")], default="DRAFT", max_length=16)),
                ("is_posted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("paid_from", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payroll_runs", to="finance.cashaccount")),
            ],
            options={"ordering": ("-period_end", "name")},
        ),
        migrations.CreateModel(
            name="PayrollItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("staff_name", models.CharField(max_length=160)),
                ("staff_reference", models.CharField(blank=True, max_length=80)),
                ("gross_pay", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("deductions", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("net_pay", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("payroll_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="finance.payrollrun")),
            ],
            options={"ordering": ("staff_name",)},
        ),
        migrations.CreateModel(
            name="BankReconciliation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("statement_date", models.DateField()),
                ("statement_balance", models.DecimalField(decimal_places=2, max_digits=14)),
                ("system_balance", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("difference", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("notes", models.TextField(blank=True)),
                ("is_reconciled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("cash_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reconciliations", to="finance.cashaccount")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-statement_date",)},
        ),
        migrations.CreateModel(
            name="FeeAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("adjustment_type", models.CharField(choices=[("DISCOUNT", "Discount"), ("BURSARY", "Bursary"), ("SCHOLARSHIP", "Scholarship"), ("PENALTY", "Penalty"), ("TAX", "Tax")], max_length=24)),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("is_posted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fee_adjustments", to="finance.account")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="adjustments", to="finance.invoice")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_date", models.DateField(default=django.utils.timezone.localdate)),
                ("reference", models.CharField(blank=True, db_index=True, max_length=80)),
                ("description", models.CharField(max_length=255)),
                ("source", models.CharField(choices=[("MANUAL", "Manual"), ("INVOICE", "Invoice"), ("PAYMENT", "Payment"), ("EXPENSE", "Expense"), ("PAYROLL", "Payroll"), ("ADJUSTMENT", "Fee adjustment"), ("OPENING", "Opening balance")], default="MANUAL", max_length=24)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("POSTED", "Posted"), ("REVERSED", "Reversed")], default="POSTED", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("source_adjustment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journal_entries", to="finance.feeadjustment")),
                ("source_expense", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journal_entries", to="finance.schoolexpense")),
                ("source_invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journal_entries", to="finance.invoice")),
                ("source_payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journal_entries", to="finance.payment")),
                ("source_payroll", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journal_entries", to="finance.payrollrun")),
            ],
            options={"ordering": ("-entry_date", "-id")},
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(blank=True, max_length=255)),
                ("debit", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("credit", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_lines", to="finance.account")),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="finance.journalentry")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddIndex(model_name="journalentry", index=models.Index(fields=["source", "status", "entry_date"], name="finance_journal_source_idx")),
        migrations.AddIndex(model_name="journalline", index=models.Index(fields=["account"], name="finance_journalline_account_idx")),
    ]
