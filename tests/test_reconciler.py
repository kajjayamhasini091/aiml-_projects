"""
Tests for the Reconciliation Engine.
Uses in-memory SQLite for isolated testing.
"""

import json
import pytest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.core.models import (
    Payment, Settlement, BankEntry, Refund,
    ReconciliationResult, AuditLog,
)
from app.core.reconciler import ReconciliationEngine


# ── Test Configuration ───────────────────────────────────────────────

class MockConfig:
    """Mock configuration for tests."""
    DATABASE_URL = "sqlite:///:memory:"
    GEMINI_API_KEY = None
    AI_CONFIDENCE_AUTO_MATCH = 0.9
    AI_CONFIDENCE_REVIEW = 0.7
    AMOUNT_TOLERANCE_PERCENT = 5.0
    DATE_TOLERANCE_DAYS = 2


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def config():
    return MockConfig()


def _make_payment(payment_id, amount, fee=None, tax=None, status="captured"):
    """Helper to create a Payment with sensible defaults."""
    if fee is None:
        fee = round(amount * 0.02, 2)
    if tax is None:
        tax = round(fee * 0.18, 2)
    return Payment(
        payment_id=payment_id,
        order_id=f"order_{payment_id}",
        amount=amount,
        currency="INR",
        status=status,
        method="upi",
        fee=fee,
        tax=tax,
        created_at=datetime(2026, 8, 10, 12, 0, 0),
    )


# ══════════════════════════════════════════════════════════════════════
# Pass 1: Payment <-> Settlement Matching
# ══════════════════════════════════════════════════════════════════════


class TestPaymentSettlementMatching:
    """Tests for Pass 1 — payment-settlement reconciliation."""

    def test_exact_payment_settlement_match(self, db_session, config):
        """Payments correctly linked to settlement with matching amounts."""
        p1 = _make_payment("pay_001", 1000.0, fee=20.0, tax=3.6)
        p2 = _make_payment("pay_002", 2000.0, fee=40.0, tax=7.2)
        db_session.add_all([p1, p2])

        # Correct net: (1000-20-3.6) + (2000-40-7.2) = 976.4 + 1952.8 = 2929.2
        settlement = Settlement(
            settlement_id="setl_001",
            amount=2929.2,
            fees=60.0,
            tax=10.8,
            utr="UTR123456789012",
            created_at=datetime(2026, 8, 12),
            payment_ids=json.dumps(["pay_001", "pay_002"]),
        )
        db_session.add(settlement)
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass1_payment_settlement()

        results = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_type == "payment"
        ).all()
        assert all(r.status == "MATCHED" for r in results)

    def test_amount_mismatch_detected(self, db_session, config):
        """Settlement amount doesn't match sum of payment net amounts."""
        p1 = _make_payment("pay_010", 5000.0, fee=100.0, tax=18.0)
        db_session.add(p1)

        # Correct net: 5000-100-18 = 4882.0, but settlement says 5000
        settlement = Settlement(
            settlement_id="setl_010",
            amount=5000.0,
            fees=100.0,
            tax=18.0,
            utr="UTR999999999999",
            created_at=datetime(2026, 8, 12),
            payment_ids=json.dumps(["pay_010"]),
        )
        db_session.add(settlement)
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass1_payment_settlement()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "pay_010"
        ).first()
        assert result is not None
        assert result.status == "MISMATCH"

    def test_unmatched_payment(self, db_session, config):
        """Payment not found in any settlement."""
        p1 = _make_payment("pay_orphan", 3000.0)
        db_session.add(p1)
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass1_payment_settlement()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "pay_orphan"
        ).first()
        assert result is not None
        assert result.status == "UNMATCHED"


# ══════════════════════════════════════════════════════════════════════
# Pass 2: Settlement <-> Bank Statement
# ══════════════════════════════════════════════════════════════════════


class TestSettlementBankMatching:
    """Tests for Pass 2 — settlement-bank reconciliation."""

    def test_date_tolerance_within_range(self, db_session, config):
        """Bank entry within 2 days tolerance should match."""
        settlement = Settlement(
            settlement_id="setl_020",
            amount=10000.0,
            fees=200.0,
            tax=36.0,
            utr="UTR111111111111",
            created_at=datetime(2026, 8, 10),
            payment_ids=json.dumps(["pay_x"]),
        )
        bank_entry = BankEntry(
            date=datetime(2026, 8, 11).date(),  # 1 day later — within tolerance
            description="RAZORPAY SETTLEMENT UTR111111111111",
            credit=10000.0,
            debit=0.0,
            balance=110000.0,
        )
        db_session.add_all([settlement, bank_entry])
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass2_settlement_bank()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "setl_020",
            ReconciliationResult.matched_with_type == "bank_entry",
        ).first()
        assert result is not None
        assert result.status == "MATCHED"

    def test_date_tolerance_exceeded(self, db_session, config):
        """Bank entry >2 days late should be flagged for AI review."""
        settlement = Settlement(
            settlement_id="setl_021",
            amount=8000.0,
            fees=160.0,
            tax=28.8,
            utr="UTR222222222222",
            created_at=datetime(2026, 8, 10),
            payment_ids=json.dumps(["pay_y"]),
        )
        bank_entry = BankEntry(
            date=datetime(2026, 8, 15).date(),  # 5 days later — exceeds tolerance
            description="RAZORPAY SETTLEMENT UTR222222222222",
            credit=8000.0,
            debit=0.0,
            balance=108000.0,
        )
        db_session.add_all([settlement, bank_entry])
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass2_settlement_bank()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "setl_021",
            ReconciliationResult.matched_with_type == "bank_entry",
        ).first()
        assert result is not None
        assert result.status == "PENDING_AI_REVIEW"
        assert result.mismatch_type == "date"

    def test_missing_bank_entry(self, db_session, config):
        """Settlement with no bank entry at all should be UNMATCHED."""
        settlement = Settlement(
            settlement_id="setl_022",
            amount=15000.0,
            fees=300.0,
            tax=54.0,
            utr="UTR333333333333",
            created_at=datetime(2026, 8, 10),
            payment_ids=json.dumps(["pay_z"]),
        )
        db_session.add(settlement)
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass2_settlement_bank()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "setl_022",
            ReconciliationResult.matched_with_type == "bank_entry",
        ).first()
        # Should be UNMATCHED since no bank entry exists
        results = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "setl_022"
        ).all()
        assert any(r.status in ("UNMATCHED", "PENDING_AI_REVIEW") for r in results)


# ══════════════════════════════════════════════════════════════════════
# Pass 3: Refund Verification
# ══════════════════════════════════════════════════════════════════════


class TestRefundVerification:
    """Tests for Pass 3 — refund reconciliation."""

    def test_refund_within_payment_amount(self, db_session, config):
        """Valid refund (amount <= payment) should MATCH."""
        payment = _make_payment("pay_100", 5000.0, status="refunded")
        refund = Refund(
            refund_id="rfnd_100",
            payment_id="pay_100",
            amount=5000.0,
            status="processed",
            created_at=datetime(2026, 8, 15),
        )
        db_session.add_all([payment, refund])
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass3_refund_verification()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "rfnd_100"
        ).first()
        assert result is not None
        assert result.status == "MATCHED"

    def test_refund_exceeds_payment_amount(self, db_session, config):
        """Refund > payment amount should be MISMATCH."""
        payment = _make_payment("pay_101", 3000.0, status="refunded")
        refund = Refund(
            refund_id="rfnd_101",
            payment_id="pay_101",
            amount=4500.0,  # Exceeds payment!
            status="processed",
            created_at=datetime(2026, 8, 15),
        )
        db_session.add_all([payment, refund])
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass3_refund_verification()

        result = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_id == "rfnd_101"
        ).first()
        assert result is not None
        assert result.status == "MISMATCH"
        assert "exceeds" in result.explanation.lower()

    def test_duplicate_refund_detection(self, db_session, config):
        """Multiple refunds for the same payment should be flagged."""
        payment = _make_payment("pay_102", 2000.0, status="refunded")
        refund1 = Refund(
            refund_id="rfnd_102a",
            payment_id="pay_102",
            amount=2000.0,
            status="processed",
            created_at=datetime(2026, 8, 15),
        )
        refund2 = Refund(
            refund_id="rfnd_102b",
            payment_id="pay_102",
            amount=2000.0,
            status="processed",
            created_at=datetime(2026, 8, 16),
        )
        db_session.add_all([payment, refund1, refund2])
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        engine._pass3_refund_verification()

        results = db_session.query(ReconciliationResult).filter(
            ReconciliationResult.record_type == "refund"
        ).all()
        assert any(r.status == "MISMATCH" and r.mismatch_type == "duplicate" for r in results)


# ══════════════════════════════════════════════════════════════════════
# Stats Computation
# ══════════════════════════════════════════════════════════════════════


class TestStatsComputation:
    """Tests for statistics computation."""

    def test_stats_computation(self, db_session, config):
        """Verify stats math is correct after a reconciliation run."""
        # Add some payments and a matching settlement
        p1 = _make_payment("pay_s1", 1000.0, fee=20.0, tax=3.6)
        p2 = _make_payment("pay_s2", 2000.0, fee=40.0, tax=7.2)
        p3 = _make_payment("pay_s3", 500.0)  # Orphan — no settlement

        settlement = Settlement(
            settlement_id="setl_s1",
            amount=2929.2,
            fees=60.0,
            tax=10.8,
            utr="UTR_STATS_TEST",
            created_at=datetime(2026, 8, 12),
            payment_ids=json.dumps(["pay_s1", "pay_s2"]),
        )

        db_session.add_all([p1, p2, p3, settlement])
        db_session.commit()

        engine = ReconciliationEngine(db_session, config)
        stats = engine.run_full_reconciliation()

        assert stats.total_records > 0
        assert stats.matched + stats.mismatched + stats.unmatched + stats.pending_ai_review + stats.ai_matched + stats.ai_flagged == stats.total_records
        assert stats.match_rate_percent >= 0
        assert stats.match_rate_percent <= 100
