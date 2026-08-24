"""
SQLAlchemy ORM models and Pydantic schemas for the Razorpay AI Finance Controller.
"""

from datetime import datetime, date as date_type
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Date
from sqlalchemy.sql import func
from pydantic import BaseModel, ConfigDict

from app.db.database import Base


# ---------------------------------------------------------------------------
# SQLAlchemy ORM Models
# ---------------------------------------------------------------------------


class Payment(Base):
    """Ingested payment records from the payment gateway."""

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String, unique=True, index=True, nullable=False)
    order_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(String, nullable=False)
    method = Column(String, nullable=False)
    fee = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    created_at = Column(DateTime, nullable=False)


class Settlement(Base):
    """Ingested settlement records — grouped payments settled to merchant bank."""

    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    settlement_id = Column(String, unique=True, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    fees = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    utr = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    payment_ids = Column(Text, nullable=False)  # JSON array stored as text


class BankEntry(Base):
    """Ingested bank statement entries."""

    __tablename__ = "bank_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    credit = Column(Float, default=0.0)
    debit = Column(Float, default=0.0)
    balance = Column(Float, default=0.0)


class Refund(Base):
    """Ingested refund records."""

    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    refund_id = Column(String, unique=True, index=True, nullable=False)
    payment_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class ReconciliationResult(Base):
    """Stores the outcome of each reconciliation check."""

    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_type = Column(String, nullable=False)       # payment / settlement / refund
    record_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)             # MATCHED / MISMATCH / UNMATCHED / PENDING_AI_REVIEW / AI_MATCHED / AI_FLAGGED
    matched_with_type = Column(String, nullable=True)   # settlement / bank_entry / payment
    matched_with_id = Column(String, nullable=True)
    method = Column(String, default="deterministic")    # deterministic / ai
    confidence = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    mismatch_type = Column(String, nullable=True)       # amount / date / missing / duplicate / fee
    created_at = Column(DateTime, default=func.now())


class AuditLog(Base):
    """Immutable append-only audit trail of every reconciliation action."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    record_type = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    old_state = Column(String, nullable=True)
    new_state = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())


# ---------------------------------------------------------------------------
# Pydantic Schemas (API response models)
# ---------------------------------------------------------------------------


class PaymentSchema(BaseModel):
    """Pydantic schema for Payment API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: str
    order_id: str
    amount: float
    currency: str
    status: str
    method: str
    fee: float
    tax: float
    created_at: Optional[str] = None


class SettlementSchema(BaseModel):
    """Pydantic schema for Settlement API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    settlement_id: str
    amount: float
    fees: float
    tax: float
    utr: str
    created_at: Optional[str] = None
    payment_ids: str


class BankEntrySchema(BaseModel):
    """Pydantic schema for BankEntry API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: Optional[str] = None
    description: str
    credit: float
    debit: float
    balance: float


class RefundSchema(BaseModel):
    """Pydantic schema for Refund API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    refund_id: str
    payment_id: str
    amount: float
    status: str
    created_at: Optional[str] = None


class ReconciliationResultSchema(BaseModel):
    """Pydantic schema for ReconciliationResult API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_type: str
    record_id: str
    status: str
    matched_with_type: Optional[str] = None
    matched_with_id: Optional[str] = None
    method: str
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    mismatch_type: Optional[str] = None
    created_at: Optional[str] = None


class AuditLogSchema(BaseModel):
    """Pydantic schema for AuditLog API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    record_type: str
    record_id: str
    old_state: Optional[str] = None
    new_state: str
    reason: str
    created_at: Optional[str] = None


class ReconciliationStats(BaseModel):
    """Summary statistics for a reconciliation run."""
    total_records: int = 0
    matched: int = 0
    mismatched: int = 0
    unmatched: int = 0
    pending_ai_review: int = 0
    ai_matched: int = 0
    ai_flagged: int = 0
    match_rate_percent: float = 0.0


class UploadResponse(BaseModel):
    """Response after uploading a CSV file."""
    records_uploaded: int
    message: str


class ReconcileResponse(BaseModel):
    """Response after running the reconciliation pipeline."""
    message: str
    stats: ReconciliationStats
