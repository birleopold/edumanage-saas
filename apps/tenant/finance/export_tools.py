import csv
from io import StringIO


def rows_to_csv(headers, rows):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return stream.getvalue()


def trial_balance_csv(report_rows):
    return rows_to_csv(["code", "account", "debit", "credit", "balance"], [[r["account"].code, r["account"].name, r["debit_total"], r["credit_total"], r["balance"]] for r in report_rows])


def income_statement_csv(report):
    rows = []
    for r in report["income_rows"]:
        rows.append(["Income", r["account"].code, r["account"].name, r["amount"]])
    for r in report["expense_rows"]:
        rows.append(["Expense", r["account"].code, r["account"].name, r["amount"]])
    rows.append(["Net Income", "", "", report["net_income"]])
    return rows_to_csv(["section", "code", "account", "amount"], rows)


def balance_sheet_csv(report):
    rows = []
    for section, section_rows in report["rows"].items():
        for r in section_rows:
            rows.append([section, r["account"].code, r["account"].name, r["amount"]])
    return rows_to_csv(["section", "code", "account", "amount"], rows)


def cash_flow_csv(report):
    return rows_to_csv(["cash_account", "cash_in", "cash_out", "net"], [[r["cash_account"].name, r["cash_in"], r["cash_out"], r["net"]] for r in report["rows"]])
