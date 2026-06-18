from datetime import datetime
from decimal import Decimal
import csv

from .models import BankStatementLine


def read_date(text):
    text = (text or "").strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("Bad date")


def import_cash_rows(uploaded_file, cash_account):
    content = uploaded_file.read().decode("utf-8-sig").splitlines()
    reader = csv.DictReader(content)
    count = 0
    for row in reader:
        BankStatementLine.objects.create(
            cash_account=cash_account,
            transaction_date=read_date(row.get("date") or row.get("transaction_date")),
            description=row.get("description") or "",
            amount=Decimal(str(row.get("amount") or "0")),
            reference=row.get("reference") or row.get("ref") or "",
        )
        count += 1
    return count
