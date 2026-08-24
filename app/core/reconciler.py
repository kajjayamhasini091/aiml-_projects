"""
Deterministic Reconciliation Engine.

Implements a three-pass reconciliation pipeline:
  Pass 1: Payment <-> Settlement matching
  Pass 2: Settlement <-> Bank Statement matching
  Pass 3: Refund verification

Records are assigned a status after each pass:
  MATCHED, MISMATCH, UNMATCHED, or PENDING_AI_REVIEW.
"""

import json
import difflib
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.models import (
    Payment,
    Settlement,
    BankEntry,
    Refund,
    ReconciliationResult,
    AuditLog,
    ReconciliationStats,
)


class ReconciliationEngine:
    """
    Core reconciliation engine that matches financial records
    using deterministic rules across three passes.
    """

    def __init__(self, db: Session, config):
        self.db = db
        self.config = config

    def run_full_reconciliation(self) -> ReconciliationStats:
        """Run all three reconciliation passes and return summary stats."""
        # Clear previous results for a fresh run
        self.db.query(ReconciliationResult).delete()
        self.db.query(AuditLog).delete()
        self.db.commit()

        self._pass1_payment_settlement()
        self._pass2_settlement_bank()
        self._pass3_refund_verification()

        return self._compute_stats()

    # ------------------------------------------------------------------
    # Pass 1: Payment <-> Settlement Matching
    # ------------------------------------------------------------------

    def _pass1_payment_settlement(self):
        """
        For each settlement, verify that the grouped payments' net
        amounts match the settlement amount.
        """
        settlements = self.db.query(Settlement).all()
        matched_payment_ids = set()

        for settlement in settlements:
            try:
                pid_list = json.loads(settlement.payment_ids)
            except (json.JSONDecodeError, TypeError):
                pid_list = []

            if not pid_list:
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="UNMATCHED",
                    explanation="No payment IDs found in settlement record.",
                    mismatch_type="missing",
                )
                continue

            # Fetch all payments referenced by this settlement
            payments = (
                self.db.query(Payment)
                .filter(Payment.payment_id.in_(pid_list))
                .all()
            )
            found_ids = {p.payment_id for p in payments}
            missing_ids = set(pid_list) - found_ids

            # Calculate expected net amount
            expected_net = sum(p.amount - p.fee - p.tax for p in payments)

            if missing_ids:
                # Some referenced payments don't exist
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="MISMATCH",
                    matched_with_type="payment",
                    explanation=f"Missing payment records: {', '.join(missing_ids)}",
                    mismatch_type="missing",
                )
            elif self._amounts_match(expected_net, settlement.amount):
                # Perfect match
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="MATCHED",
                    matched_with_type="payment",
                    matched_with_id=json.dumps(pid_list),
                    explanation=f"Net amount {expected_net:.2f} matches settlement {settlement.amount:.2f}",
                )
            else:
                # Amount mismatch
                diff = abs(expected_net - settlement.amount)
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="MISMATCH",
                    matched_with_type="payment",
                    matched_with_id=json.dumps(pid_list),
                    explanation=(
                        f"Amount mismatch: expected net {expected_net:.2f}, "
                        f"got settlement {settlement.amount:.2f} "
                        f"(difference: {diff:.2f})"
                    ),
                    mismatch_type="amount",
                )

            # Mark individual payments
            for payment in payments:
                matched_payment_ids.add(payment.payment_id)
                if self._amounts_match(expected_net, settlement.amount):
                    status = "MATCHED"
                else:
                    status = "MISMATCH"
                self._create_result(
                    record_type="payment",
                    record_id=payment.payment_id,
                    status=status,
                    matched_with_type="settlement",
                    matched_with_id=settlement.settlement_id,
                    explanation=f"Part of settlement {settlement.settlement_id}",
                    mismatch_type="amount" if status == "MISMATCH" else None,
                )

        # Find payments not in any settlement
        all_payments = self.db.query(Payment).all()
        for payment in all_payments:
            if payment.payment_id not in matched_payment_ids:
                self._create_result(
                    record_type="payment",
                    record_id=payment.payment_id,
                    status="UNMATCHED",
                    explanation="Payment not found in any settlement.",
                    mismatch_type="missing",
                )

    # ------------------------------------------------------------------
    # Pass 2: Settlement <-> Bank Statement Matching
    # ------------------------------------------------------------------

    def _pass2_settlement_bank(self):
        """
        Match each settlement's UTR to bank statement entries and
        verify the credited amount and date.
        """
        settlements = self.db.query(Settlement).all()
        bank_entries = self.db.query(BankEntry).all()

        for settlement in settlements:
            utr = settlement.utr.strip()
            best_match = None
            best_ratio = 0.0

            for entry in bank_entries:
                desc = entry.description.strip()
                # Exact UTR match (case-insensitive, ignore spaces)
                if utr.lower().replace(" ", "") in desc.lower().replace(" ", ""):
                    best_match = entry
                    best_ratio = 1.0
                    break

            # If no exact match, try fuzzy matching on descriptions
            if best_match is None:
                for entry in bank_entries:
                    ratio = difflib.SequenceMatcher(
                        None,
                        utr.lower(),
                        entry.description.lower(),
                    ).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = entry

            if best_match is None or best_ratio < 0.4:
                # No bank entry found for this settlement
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="UNMATCHED",
                    explanation=f"No bank entry found for UTR {utr}",
                    mismatch_type="missing",
                    method="deterministic",
                )
                continue

            # Check amount match
            amount_ok = self._amounts_match(settlement.amount, best_match.credit)

            # Check date tolerance
            settlement_date = settlement.created_at.date() if settlement.created_at else None
            bank_date = best_match.date
            date_ok = True
            if settlement_date and bank_date:
                day_diff = abs((bank_date - settlement_date).days)
                date_ok = day_diff <= self.config.DATE_TOLERANCE_DAYS

            if amount_ok and date_ok and best_ratio >= 0.8:
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="MATCHED",
                    matched_with_type="bank_entry",
                    matched_with_id=str(best_match.id),
                    explanation=(
                        f"UTR {utr} matched bank entry (credit: {best_match.credit:.2f}, "
                        f"date: {best_match.date})"
                    ),
                    method="deterministic",
                )
            elif not amount_ok:
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="MISMATCH",
                    matched_with_type="bank_entry",
                    matched_with_id=str(best_match.id),
                    explanation=(
                        f"Amount mismatch: settlement {settlement.amount:.2f} vs "
                        f"bank credit {best_match.credit:.2f}"
                    ),
                    mismatch_type="amount",
                    method="deterministic",
                )
            elif not date_ok:
                # Date is outside tolerance — send to AI for analysis
                day_diff = abs((bank_date - settlement_date).days) if settlement_date and bank_date else 0
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="PENDING_AI_REVIEW",
                    matched_with_type="bank_entry",
                    matched_with_id=str(best_match.id),
                    explanation=(
                        f"Date mismatch: settlement on {settlement_date}, "
                        f"bank credit on {bank_date} ({day_diff} days apart). "
                        f"Possible delayed credit."
                    ),
                    mismatch_type="date",
                    method="deterministic",
                )
            elif best_ratio < 0.8:
                # Fuzzy UTR match — send to AI
                self._create_result(
                    record_type="settlement",
                    record_id=settlement.settlement_id,
                    status="PENDING_AI_REVIEW",
                    matched_with_type="bank_entry",
                    matched_with_id=str(best_match.id),
                    explanation=(
                        f"Fuzzy UTR match ({best_ratio:.0%} similarity): "
                        f"'{utr}' vs '{best_match.description}'. Needs AI verification."
                    ),
                    mismatch_type="missing",
                    method="deterministic",
                )

    # ------------------------------------------------------------------
    # Pass 3: Refund Verification
    # ------------------------------------------------------------------

    def _pass3_refund_verification(self):
        """
        Verify each refund against its original payment: amount validity,
        payment existence, and duplicate detection.
        """
        refunds = self.db.query(Refund).all()

        # Detect duplicate refunds (multiple refunds for same payment)
        payment_refund_count: dict[str, int] = {}
        for refund in refunds:
            payment_refund_count[refund.payment_id] = (
                payment_refund_count.get(refund.payment_id, 0) + 1
            )

        for refund in refunds:
            payment = (
                self.db.query(Payment)
                .filter(Payment.payment_id == refund.payment_id)
                .first()
            )

            if payment is None:
                self._create_result(
                    record_type="refund",
                    record_id=refund.refund_id,
                    status="MISMATCH",
                    explanation=f"Original payment {refund.payment_id} not found.",
                    mismatch_type="missing",
                )
                continue

            issues = []

            # Check refund amount doesn't exceed payment
            if refund.amount > payment.amount:
                issues.append(
                    f"Refund amount ({refund.amount:.2f}) exceeds payment "
                    f"amount ({payment.amount:.2f})"
                )

            # Check for duplicate refunds
            if payment_refund_count.get(refund.payment_id, 0) > 1:
                issues.append(
                    f"Duplicate refund detected: {payment_refund_count[refund.payment_id]} "
                    f"refunds for payment {refund.payment_id}"
                )

            if issues:
                mismatch_type = "amount" if refund.amount > payment.amount else "duplicate"
                self._create_result(
                    record_type="refund",
                    record_id=refund.refund_id,
                    status="MISMATCH",
                    matched_with_type="payment",
                    matched_with_id=payment.payment_id,
                    explanation="; ".join(issues),
                    mismatch_type=mismatch_type,
                )
            else:
                self._create_result(
                    record_type="refund",
                    record_id=refund.refund_id,
                    status="MATCHED",
                    matched_with_type="payment",
                    matched_with_id=payment.payment_id,
                    explanation=(
                        f"Valid refund of {refund.amount:.2f} against "
                        f"payment of {payment.amount:.2f}"
                    ),
                )

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _amounts_match(self, a: float, b: float) -> bool:
        """Check if two amounts are within the configured tolerance."""
        if a == 0 and b == 0:
            return True
        denominator = max(abs(a), abs(b), 1.0)
        pct_diff = abs(a - b) / denominator * 100
        return pct_diff <= self.config.AMOUNT_TOLERANCE_PERCENT

    def _compute_stats(self) -> ReconciliationStats:
        """Query the results table and compute summary statistics."""
        results = self.db.query(ReconciliationResult).all()
        total = len(results)
        matched = sum(1 for r in results if r.status == "MATCHED")
        mismatched = sum(1 for r in results if r.status == "MISMATCH")
        unmatched = sum(1 for r in results if r.status == "UNMATCHED")
        pending = sum(1 for r in results if r.status == "PENDING_AI_REVIEW")
        ai_matched = sum(1 for r in results if r.status == "AI_MATCHED")
        ai_flagged = sum(1 for r in results if r.status == "AI_FLAGGED")

        match_rate = (matched + ai_matched) / total * 100 if total > 0 else 0.0

        return ReconciliationStats(
            total_records=total,
            matched=matched,
            mismatched=mismatched,
            unmatched=unmatched,
            pending_ai_review=pending,
            ai_matched=ai_matched,
            ai_flagged=ai_flagged,
            match_rate_percent=round(match_rate, 2),
        )

    def _create_result(
        self,
        record_type: str,
        record_id: str,
        status: str,
        matched_with_type: str = None,
        matched_with_id: str = None,
        explanation: str = "",
        mismatch_type: str = None,
        method: str = "deterministic",
    ):
        """Create a ReconciliationResult and an AuditLog entry."""
        result = ReconciliationResult(
            record_type=record_type,
            record_id=record_id,
            status=status,
            matched_with_type=matched_with_type,
            matched_with_id=matched_with_id,
            method=method,
            explanation=explanation,
            mismatch_type=mismatch_type,
        )
        self.db.add(result)

        self._log_audit(
            action="reconciliation",
            record_type=record_type,
            record_id=record_id,
            old_state="PENDING",
            new_state=status,
            reason=explanation,
        )

        self.db.commit()

    def _log_audit(
        self,
        action: str,
        record_type: str,
        record_id: str,
        old_state: str,
        new_state: str,
        reason: str,
    ):
        """Append an entry to the immutable audit log."""
        log = AuditLog(
            action=action,
            record_type=record_type,
            record_id=record_id,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
        )
        self.db.add(log)
