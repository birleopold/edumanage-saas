from decimal import Decimal

from django.db import models
from django.utils import timezone


class Account(models.Model):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    ACCOUNT_TYPE_CHOICES = ((ASSET, "Asset"), (LIABILITY, "Liability"), (EQUITY, "Equity"), (INCOME, "Income"), (EXPENSE, "Expense"))
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    account_type = models.CharField(max_length=16, choices=ACCOUNT_TYPE_CHOICES)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_control_account = models.BooleanField(default=False)
    is_bank_or_cash = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} - {self.name}"


class CashAccount(models.Model):
    CASH = "CASH"
    BANK = "BANK"
    MOBILE_MONEY = "MOBILE_MONEY"
    CARD = "CARD"
    ACCOUNT_KIND_CHOICES = ((CASH, "Cash"), (BANK, "Bank"), (MOBILE_MONEY, "Mobile money"), (CARD, "Card/Card settlement"))
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=ACCOUNT_KIND_CHOICES)
    ledger_account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="cash_accounts")
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=80, blank=True)
    mobile_network = models.CharField(max_length=32, blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("kind", "name")

    def __str__(self):
        return self.name


class JournalEntry(models.Model):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"
    STATUS_CHOICES = ((DRAFT, "Draft"), (POSTED, "Posted"), (REVERSED, "Reversed"))
    MANUAL = "MANUAL"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    EXPENSE = "EXPENSE"
    PAYROLL = "PAYROLL"
    ADJUSTMENT = "ADJUSTMENT"
    OPENING = "OPENING"
    SOURCE_CHOICES = ((MANUAL, "Manual"), (INVOICE, "Invoice"), (PAYMENT, "Payment"), (EXPENSE, "Expense"), (PAYROLL, "Payroll"), (ADJUSTMENT, "Fee adjustment"), (OPENING, "Opening balance"))
    entry_date = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=80, blank=True, db_index=True)
    description = models.CharField(max_length=255)
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=MANUAL)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=POSTED)
    source_invoice = models.ForeignKey("finance.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries")
    source_payment = models.ForeignKey("finance.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries")
    source_adjustment = models.ForeignKey("finance.FeeAdjustment", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries")
    source_expense = models.ForeignKey("finance.SchoolExpense", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries")
    source_payroll = models.ForeignKey("finance.PayrollRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries")
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "finance"
        ordering = ("-entry_date", "-id")
        indexes = [models.Index(fields=["source", "status", "entry_date"])]

    def __str__(self):
        return self.reference or f"Journal #{self.id}"

    def total_debit(self):
        return sum((line.debit for line in self.lines.all()), Decimal("0"))

    def total_credit(self):
        return sum((line.credit for line in self.lines.all()), Decimal("0"))

    def is_balanced(self):
        return self.total_debit() == self.total_credit()


class JournalLine(models.Model):
    entry = models.ForeignKey("finance.JournalEntry", on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="journal_lines")
    description = models.CharField(max_length=255, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        app_label = "finance"
        ordering = ("id",)
        indexes = [models.Index(fields=["account"])]

    def __str__(self):
        return f"{self.entry} - {self.account}"


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    expense_account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="expense_categories")
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "finance"
        ordering = ("name",)

    def __str__(self):
        return self.name


class SchoolExpense(models.Model):
    expense_date = models.DateField(default=timezone.localdate)
    category = models.ForeignKey("finance.ExpenseCategory", on_delete=models.PROTECT, related_name="expenses")
    paid_from = models.ForeignKey("finance.CashAccount", on_delete=models.PROTECT, related_name="expenses")
    supplier = models.CharField(max_length=160, blank=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=80, blank=True)
    is_posted = models.BooleanField(default=False)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-expense_date", "-id")

    def __str__(self):
        return f"{self.expense_date} - {self.description}"


class PayrollRun(models.Model):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PAID = "PAID"
    STATUS_CHOICES = ((DRAFT, "Draft"), (APPROVED, "Approved"), (PAID, "Paid"))
    name = models.CharField(max_length=120)
    period_start = models.DateField()
    period_end = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    paid_from = models.ForeignKey("finance.CashAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_runs")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    is_posted = models.BooleanField(default=False)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-period_end", "name")

    def __str__(self):
        return self.name

    def total_net_pay(self):
        return sum((item.net_pay for item in self.items.all()), Decimal("0"))


class PayrollItem(models.Model):
    payroll_run = models.ForeignKey("finance.PayrollRun", on_delete=models.CASCADE, related_name="items")
    staff_name = models.CharField(max_length=160)
    staff_reference = models.CharField(max_length=80, blank=True)
    gross_pay = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    deductions = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = "finance"
        ordering = ("staff_name",)

    def save(self, *args, **kwargs):
        self.net_pay = (self.gross_pay or Decimal("0")) - (self.deductions or Decimal("0"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.payroll_run} - {self.staff_name}"


class BankReconciliation(models.Model):
    cash_account = models.ForeignKey("finance.CashAccount", on_delete=models.PROTECT, related_name="reconciliations")
    statement_date = models.DateField()
    statement_balance = models.DecimalField(max_digits=14, decimal_places=2)
    system_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    difference = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    is_reconciled = models.BooleanField(default=False)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-statement_date",)

    def save(self, *args, **kwargs):
        self.difference = (self.statement_balance or Decimal("0")) - (self.system_balance or Decimal("0"))
        self.is_reconciled = self.difference == Decimal("0")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cash_account} - {self.statement_date}"


class BankStatementLine(models.Model):
    cash_account = models.ForeignKey("finance.CashAccount", on_delete=models.PROTECT, related_name="statement_lines")
    transaction_date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    matched_payment = models.ForeignKey("finance.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="statement_matches")
    is_reconciled = models.BooleanField(default=False)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-transaction_date", "-id")
        indexes = [models.Index(fields=["cash_account", "transaction_date"]), models.Index(fields=["reference"])]

    def __str__(self):
        return f"{self.transaction_date} {self.amount} {self.reference}"


class FeeAdjustment(models.Model):
    DISCOUNT = "DISCOUNT"
    BURSARY = "BURSARY"
    SCHOLARSHIP = "SCHOLARSHIP"
    PENALTY = "PENALTY"
    TAX = "TAX"
    ADJUSTMENT_TYPE_CHOICES = ((DISCOUNT, "Discount"), (BURSARY, "Bursary"), (SCHOLARSHIP, "Scholarship"), (PENALTY, "Penalty"), (TAX, "Tax"))
    REDUCE_TYPES = {DISCOUNT, BURSARY, SCHOLARSHIP}
    invoice = models.ForeignKey("finance.Invoice", on_delete=models.CASCADE, related_name="adjustments")
    adjustment_type = models.CharField(max_length=24, choices=ADJUSTMENT_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="fee_adjustments")
    is_posted = models.BooleanField(default=False)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-created_at",)

    def signed_amount(self):
        amount = self.amount or Decimal("0")
        return -amount if self.adjustment_type in self.REDUCE_TYPES else amount

    def __str__(self):
        return f"{self.get_adjustment_type_display()} {self.amount} - {self.invoice}"
