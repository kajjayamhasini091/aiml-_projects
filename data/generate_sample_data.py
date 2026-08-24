"""
Sample Data Generator for the Razorpay AI Finance Controller.

Generates realistic CSV datasets with deliberate mismatches for demo:
- payments.csv (50 records)
- settlements.csv (10 records, 2 with amount mismatches)
- bank_statement.csv (with delayed/missing/mangled entries)
- refunds.csv (5 records, 1 exceeding payment, 1 duplicate)
"""

import csv
import json
import os
import random
import string
from datetime import datetime, timedelta

# Reproducible random data
random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def rand_id(prefix: str, length: int = 14) -> str:
    """Generate a random ID like pay_AbCdEf123456."""
    chars = string.ascii_letters + string.digits
    return prefix + "".join(random.choices(chars, k=length))


def rand_date(start: datetime, end: datetime) -> datetime:
    """Generate a random datetime between start and end."""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def generate_payments(n: int = 50):
    """Generate payment records."""
    methods = ["upi", "card", "netbanking", "wallet"]
    start = datetime(2026, 8, 1)
    end = datetime(2026, 8, 20)

    payments = []
    for _ in range(n):
        amount = round(random.uniform(500, 50000), 2)
        fee = round(amount * 0.02, 2)        # 2% MDR
        tax = round(fee * 0.18, 2)           # 18% GST on fee
        status = "captured"
        method = random.choice(methods)
        created_at = rand_date(start, end)

        payments.append({
            "payment_id": rand_id("pay_"),
            "order_id": rand_id("order_"),
            "amount": amount,
            "currency": "INR",
            "status": status,
            "method": method,
            "fee": fee,
            "tax": tax,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Mark some as refunded (for refund testing)
    for i in [5, 12, 20, 30, 40]:
        if i < len(payments):
            payments[i]["status"] = "refunded"

    return payments


def generate_settlements(payments):
    """Group payments into settlements. Introduce 2 amount mismatches."""
    settlements = []
    chunk_size = 5

    for i in range(0, len(payments), chunk_size):
        chunk = payments[i : i + chunk_size]
        pid_list = [p["payment_id"] for p in chunk]

        # Calculate correct net amount
        net_amount = sum(p["amount"] - p["fee"] - p["tax"] for p in chunk)
        total_fees = sum(p["fee"] for p in chunk)
        total_tax = sum(p["tax"] for p in chunk)

        # Settlement date is 1-2 days after latest payment in the group
        latest_payment_date = max(
            datetime.strptime(p["created_at"], "%Y-%m-%d %H:%M:%S") for p in chunk
        )
        settlement_date = latest_payment_date + timedelta(days=random.choice([1, 2]))

        settlement = {
            "settlement_id": rand_id("setl_"),
            "amount": round(net_amount, 2),
            "fees": round(total_fees, 2),
            "tax": round(total_tax, 2),
            "utr": "UTR" + "".join(random.choices(string.digits, k=12)),
            "created_at": settlement_date.strftime("%Y-%m-%d %H:%M:%S"),
            "payment_ids": json.dumps(pid_list),
        }
        settlements.append(settlement)

    # Introduce amount mismatches in settlements 2 and 7 (off by 15-45 INR)
    if len(settlements) > 2:
        settlements[2]["amount"] = round(settlements[2]["amount"] + 27.50, 2)
    if len(settlements) > 7:
        settlements[7]["amount"] = round(settlements[7]["amount"] - 18.75, 2)

    return settlements


def generate_bank_statement(settlements):
    """Generate bank statement entries. Introduce mismatches."""
    entries = []
    balance = 100000.00

    for idx, s in enumerate(settlements):
        settlement_date = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S").date()
        credit = s["amount"]
        utr = s["utr"]

        # Normal entry
        bank_date = settlement_date
        description = f"RAZORPAY SETTLEMENT {utr}"

        # Introduce mismatches for specific entries
        if idx == 1:
            # Rounding error: slightly different amount
            credit = round(credit + 3.47, 2)
        elif idx == 3:
            # Delayed credit: 3 days later
            bank_date = settlement_date + timedelta(days=3)
        elif idx == 5:
            # Skip this settlement entirely (missing bank entry)
            continue
        elif idx == 6:
            # Mangled UTR in description
            description = f"RAZORPAY SETTL {utr[:6]} {utr[6:]}"

        balance = round(balance + credit, 2)
        entries.append({
            "date": bank_date.strftime("%Y-%m-%d"),
            "description": description,
            "credit": credit,
            "debit": 0.00,
            "balance": balance,
        })

    return entries


def generate_refunds(payments):
    """Generate refund records with deliberate issues."""
    refunded_payments = [p for p in payments if p["status"] == "refunded"]
    refunds = []

    for i, payment in enumerate(refunded_payments):
        refund_date = datetime.strptime(payment["created_at"], "%Y-%m-%d %H:%M:%S") + timedelta(days=random.randint(1, 5))

        refund = {
            "refund_id": rand_id("rfnd_"),
            "payment_id": payment["payment_id"],
            "amount": payment["amount"],  # Full refund
            "status": "processed",
            "created_at": refund_date.strftime("%Y-%m-%d %H:%M:%S"),
        }
        refunds.append(refund)

    # Mismatch 1: Refund exceeding payment amount (on the first refund)
    if len(refunds) > 0:
        refunds[0]["amount"] = round(refunds[0]["amount"] * 1.5, 2)

    # Mismatch 2: Duplicate refund for the second refunded payment
    if len(refunds) > 1:
        duplicate = refunds[1].copy()
        duplicate["refund_id"] = rand_id("rfnd_")
        duplicate["created_at"] = (
            datetime.strptime(duplicate["created_at"], "%Y-%m-%d %H:%M:%S")
            + timedelta(hours=3)
        ).strftime("%Y-%m-%d %H:%M:%S")
        refunds.append(duplicate)

    return refunds


def write_csv(filename, data, fieldnames):
    """Write a list of dicts to a CSV file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"  ✅ Generated {filepath} ({len(data)} records)")


def main():
    """Generate all sample CSV files."""
    print("\n🔧 Generating sample data for Razorpay AI Finance Controller...\n")

    # Generate payments
    payments = generate_payments(50)
    write_csv(
        "payments.csv",
        payments,
        ["payment_id", "order_id", "amount", "currency", "status", "method", "fee", "tax", "created_at"],
    )

    # Generate settlements (grouped from payments)
    settlements = generate_settlements(payments)
    write_csv(
        "settlements.csv",
        settlements,
        ["settlement_id", "amount", "fees", "tax", "utr", "created_at", "payment_ids"],
    )

    # Generate bank statement
    bank_entries = generate_bank_statement(settlements)
    write_csv(
        "bank_statement.csv",
        bank_entries,
        ["date", "description", "credit", "debit", "balance"],
    )

    # Generate refunds
    refunds = generate_refunds(payments)
    write_csv(
        "refunds.csv",
        refunds,
        ["refund_id", "payment_id", "amount", "status", "created_at"],
    )

    print(f"\n✨ All sample data generated in: {OUTPUT_DIR}")
    print("   Deliberate mismatches introduced:")
    print("   - 2 settlements with incorrect amounts")
    print("   - 1 bank entry with amount rounding error")
    print("   - 1 bank entry with 3-day delay (late credit)")
    print("   - 1 settlement missing from bank statement")
    print("   - 1 bank entry with mangled UTR description")
    print("   - 1 refund exceeding original payment amount")
    print("   - 1 duplicate refund for the same payment")
    print()


if __name__ == "__main__":
    main()
