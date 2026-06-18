from .models import Account, CashAccount, ExpenseCategory


DEFAULT_ACCOUNTS = {
    "1000": ("Cash on Hand", Account.ASSET, True),
    "1010": ("Bank Account", Account.ASSET, True),
    "1020": ("Mobile Money Account", Account.ASSET, True),
    "1100": ("Accounts Receivable - Fees", Account.ASSET, False),
    "2000": ("Accounts Payable", Account.LIABILITY, False),
    "2100": ("Tax Payable", Account.LIABILITY, False),
    "3000": ("Opening Balance Equity", Account.EQUITY, False),
    "4000": ("Tuition and School Fees Income", Account.INCOME, False),
    "4050": ("Discounts, Bursaries and Scholarships", Account.EXPENSE, False),
    "4100": ("Penalty Income", Account.INCOME, False),
    "5000": ("Payroll Expense", Account.EXPENSE, False),
    "5100": ("General School Expenses", Account.EXPENSE, False),
    "5200": ("Taxes and Statutory Charges", Account.EXPENSE, False),
}


def setup_default_chart_of_accounts():
    created = []
    accounts = {}
    for code, values in DEFAULT_ACCOUNTS.items():
        name, account_type, bank_or_cash = values
        obj, was_created = Account.objects.get_or_create(
            code=code,
            defaults={"name": name, "account_type": account_type, "is_bank_or_cash": bank_or_cash},
        )
        accounts[code] = obj
        if was_created:
            created.append(obj)
    CashAccount.objects.get_or_create(name="Main Cash", defaults={"kind": CashAccount.CASH, "ledger_account": accounts["1000"]})
    CashAccount.objects.get_or_create(name="Main Bank", defaults={"kind": CashAccount.BANK, "ledger_account": accounts["1010"]})
    CashAccount.objects.get_or_create(name="Main Mobile Money", defaults={"kind": CashAccount.MOBILE_MONEY, "ledger_account": accounts["1020"]})
    ExpenseCategory.objects.get_or_create(name="General Expenses", defaults={"expense_account": accounts["5100"]})
    ExpenseCategory.objects.get_or_create(name="Payroll", defaults={"expense_account": accounts["5000"]})
    return {"created_count": len(created), "accounts": accounts}


def get_account(code):
    setup_default_chart_of_accounts()
    return Account.objects.get(code=code)
