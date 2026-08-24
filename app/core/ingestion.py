"""
CSV ingestion and parsing module.
Parses uploaded CSV files (payments, settlements, bank statements, refunds)
and stores normalized records into the database.
"""

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.models import Payment, Settlement, BankEntry, Refund


def _decode_content(file_content: bytes) -> str:
    """Decode file bytes, stripping BOM if present."""
    text = file_content.decode("utf-8-sig")
    return text.strip()


def _parse_datetime(value: str) -> datetime:
    """Parse a datetime string, trying multiple common formats."""
    value = value.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime: {value}")


def _parse_date(value: str):
    """Parse a date string and return a date object."""
    return _parse_datetime(value).date()


def _safe_float(value: str, default: float = 0.0) -> float:
    """Safely parse a float from a string."""
    try:
        return float(value.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return default


def parse_payments_csv(file_content: bytes, db: Session) -> int:
    """
    Parse a payments CSV file and insert records into the database.

    Expected columns: payment_id, order_id, amount, currency, status,
                      method, fee, tax, created_at

    Returns the number of records inserted.
    """
    text = _decode_content(file_content)
    reader = csv.DictReader(io.StringIO(text))
    count = 0

    for row in reader:
        payment = Payment(
            payment_id=row["payment_id"].strip(),
            order_id=row["order_id"].strip(),
            amount=_safe_float(row["amount"]),
            currency=row.get("currency", "INR").strip(),
            status=row["status"].strip(),
            method=row["method"].strip(),
            fee=_safe_float(row.get("fee", "0")),
            tax=_safe_float(row.get("tax", "0")),
            created_at=_parse_datetime(row["created_at"]),
        )
        db.add(payment)
        count += 1

    db.commit()
    return count


def parse_settlements_csv(file_content: bytes, db: Session) -> int:
    """
    Parse a settlements CSV file and insert records into the database.

    Expected columns: settlement_id, amount, fees, tax, utr, created_at, payment_ids

    Returns the number of records inserted.
    """
    text = _decode_content(file_content)
    reader = csv.DictReader(io.StringIO(text))
    count = 0

    for row in reader:
        settlement = Settlement(
            settlement_id=row["settlement_id"].strip(),
            amount=_safe_float(row["amount"]),
            fees=_safe_float(row.get("fees", "0")),
            tax=_safe_float(row.get("tax", "0")),
            utr=row["utr"].strip(),
            created_at=_parse_datetime(row["created_at"]),
            payment_ids=row["payment_ids"].strip(),
        )
        db.add(settlement)
        count += 1

    db.commit()
    return count


def parse_bank_statement_csv(file_content: bytes, db: Session) -> int:
    """
    Parse a bank statement CSV file and insert records into the database.

    Expected columns: date, description, credit, debit, balance

    Returns the number of records inserted.
    """
    text = _decode_content(file_content)
    reader = csv.DictReader(io.StringIO(text))
    count = 0

    for row in reader:
        entry = BankEntry(
            date=_parse_date(row["date"]),
            description=row["description"].strip(),
            credit=_safe_float(row.get("credit", "0")),
            debit=_safe_float(row.get("debit", "0")),
            balance=_safe_float(row.get("balance", "0")),
        )
        db.add(entry)
        count += 1

    db.commit()
    return count


def parse_refunds_csv(file_content: bytes, db: Session) -> int:
    """
    Parse a refunds CSV file and insert records into the database.

    Expected columns: refund_id, payment_id, amount, status, created_at

    Returns the number of records inserted.
    """
    text = _decode_content(file_content)
    reader = csv.DictReader(io.StringIO(text))
    count = 0

    for row in reader:
        refund = Refund(
            refund_id=row["refund_id"].strip(),
            payment_id=row["payment_id"].strip(),
            amount=_safe_float(row["amount"]),
            status=row["status"].strip(),
            created_at=_parse_datetime(row["created_at"]),
        )
        db.add(refund)
        count += 1

    db.commit()
    return count
