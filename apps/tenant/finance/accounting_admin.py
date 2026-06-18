from django.contrib import admin

from .models import Account, BankReconciliation, CashAccount, ExpenseCategory, FeeAdjustment, JournalEntry, JournalLine, PayrollItem, PayrollRun, SchoolExpense


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "is_bank_or_cash", "is_active")
    list_filter = ("account_type", "is_bank_or_cash", "is_active")
    search_fields = ("code", "name")


@admin.register(CashAccount)
class CashAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "ledger_account", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "bank_name", "account_number", "mobile_network")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("entry_date", "reference", "description", "source", "status")
    list_filter = ("source", "status", "entry_date")
    search_fields = ("reference", "description")
    inlines = (JournalLineInline,)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "expense_account", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(SchoolExpense)
class SchoolExpenseAdmin(admin.ModelAdmin):
    list_display = ("expense_date", "category", "description", "amount", "paid_from", "is_posted")
    list_filter = ("is_posted", "category", "expense_date")
    search_fields = ("description", "supplier", "reference")


class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("name", "period_start", "period_end", "payment_date", "status", "is_posted")
    list_filter = ("status", "is_posted")
    search_fields = ("name",)
    inlines = (PayrollItemInline,)


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ("cash_account", "statement_date", "statement_balance", "system_balance", "difference", "is_reconciled")
    list_filter = ("is_reconciled", "statement_date")
    search_fields = ("cash_account__name",)


@admin.register(FeeAdjustment)
class FeeAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "adjustment_type", "description", "amount", "is_posted", "created_at")
    list_filter = ("adjustment_type", "is_posted")
    search_fields = ("invoice__reference", "description")
