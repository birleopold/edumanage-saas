import csv
from io import BytesIO, StringIO

from openpyxl import Workbook


def rows_to_csv(headers, rows):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return stream.getvalue()


def rows_to_xlsx(headers, rows, sheet_name="Report"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    ws.append(headers)
    for row in rows:
        ws.append(list(row))
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def trial_balance_rows(report_rows):
    return [[r["account"].code, r["account"].name, r["debit_total"], r["credit_total"], r["balance"]] for r in report_rows]


def trial_balance_csv(report_rows):
    return rows_to_csv(["code", "account", "debit", "credit", "balance"], trial_balance_rows(report_rows))


def trial_balance_xlsx(report_rows):
    return rows_to_xlsx(["code", "account", "debit", "credit", "balance"], trial_balance_rows(report_rows), "Trial Balance")


def income_statement_rows(report):
    rows = []
    for r in report["income_rows"]:
        rows.append(["Income", r["account"].code, r["account"].name, r["amount"]])
    for r in report["expense_rows"]:
        rows.append(["Expense", r["account"].code, r["account"].name, r["amount"]])
    rows.append(["Net Income", "", "", report["net_income"]])
    return rows


def income_statement_csv(report):
    return rows_to_csv(["section", "code", "account", "amount"], income_statement_rows(report))


def income_statement_xlsx(report):
    return rows_to_xlsx(["section", "code", "account", "amount"], income_statement_rows(report), "Income")


def balance_sheet_rows(report):
    rows = []
    for section, section_rows in report["rows"].items():
        for r in section_rows:
            rows.append([section, r["account"].code, r["account"].name, r["amount"]])
    return rows


def balance_sheet_csv(report):
    return rows_to_csv(["section", "code", "account", "amount"], balance_sheet_rows(report))


def balance_sheet_xlsx(report):
    return rows_to_xlsx(["section", "code", "account", "amount"], balance_sheet_rows(report), "Position")


def cash_flow_rows(report):
    return [[r["cash_account"].name, r["cash_in"], r["cash_out"], r["net"]] for r in report["rows"]]


def cash_flow_csv(report):
    return rows_to_csv(["cash_account", "cash_in", "cash_out", "net"], cash_flow_rows(report))


def cash_flow_xlsx(report):
    return rows_to_xlsx(["cash_account", "cash_in", "cash_out", "net"], cash_flow_rows(report), "Cash Flow")
