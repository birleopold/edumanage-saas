from django.urls import path
from . import accounting_views

urlpatterns = [
    path("", accounting_views.accounting_dashboard, name="finance_books_home"),
    path("chart/", accounting_views.chart_of_accounts, name="finance_books_chart"),
    path("money/", accounting_views.cash_accounts, name="finance_books_money"),
    path("journals/", accounting_views.journal_entries, name="finance_books_journals"),
    path("cost/new/", accounting_views.expense_create, name="finance_books_cost_new"),
    path("staffpay/new/", accounting_views.payroll_create, name="finance_books_staffpay_new"),
    path("upload/", accounting_views.statement_import, name="finance_books_upload"),
    path("trial/", accounting_views.trial_balance_report, name="finance_books_trial"),
    path("income/", accounting_views.income_statement_report, name="finance_books_income"),
    path("position/", accounting_views.balance_sheet_report, name="finance_books_position"),
    path("cash-flow/", accounting_views.cash_flow_report, name="finance_books_cash_flow"),
]
