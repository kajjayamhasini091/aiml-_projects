"""
AI Reasoning Layer for ambiguous reconciliation cases.

Uses Google Gemini API for intelligent mismatch analysis when available,
with a heuristic fallback when no API key is configured. Enforces guardrails
to ensure AI cannot override financial invariants.
"""

import json
import difflib
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.models import (
    ReconciliationResult,
    AuditLog,
    Payment,
    Settlement,
    BankEntry,
)

logger = logging.getLogger(__name__)


class AIReasoner:
    """
    AI-powered reasoning for ambiguous reconciliation cases.

    Applies LLM analysis (Gemini) when available, with heuristic fallback.
    All AI recommendations are subject to financial guardrails.
    """

    def __init__(self, config):
        self.config = config
        self.use_llm = bool(config.GEMINI_API_KEY)
        self.model = None

        if self.use_llm:
            try:
                import google.generativeai as genai

                genai.configure(api_key=config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("AI Reasoner initialized with Gemini LLM.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}. Using heuristic fallback.")
                self.use_llm = False
        else:
            logger.info("No GEMINI_API_KEY set. AI Reasoner using heuristic fallback.")

    def analyze_mismatch(
        self,
        record_type: str,
        record_data: dict,
        matched_candidate_data: dict,
    ) -> dict:
        """
        Analyze an ambiguous mismatch case and return a recommendation.

        Returns:
            dict with keys:
                - recommendation: 'match' | 'flag' | 'escalate'
                - confidence: float 0.0-1.0
                - explanation: str
        """
        if self.use_llm and self.model:
            result = self._llm_analysis(record_type, record_data, matched_candidate_data)
        else:
            result = self._heuristic_analysis(record_type, record_data, matched_candidate_data)

        # Apply guardrails — these can override AI recommendations
        result = self._apply_guardrails(result, record_data, matched_candidate_data)

        return result

    def process_pending_reviews(self, db: Session):
        """
        Process all records with PENDING_AI_REVIEW status.
        Updates their status based on AI analysis + guardrails.
        """
        pending = (
            db.query(ReconciliationResult)
            .filter(ReconciliationResult.status == "PENDING_AI_REVIEW")
            .all()
        )

        logger.info(f"Processing {len(pending)} pending AI reviews.")

        for result in pending:
            # Gather context records from the database
            record_data = self._get_record_data(db, result.record_type, result.record_id)
            candidate_data = {}
            if result.matched_with_type and result.matched_with_id:
                candidate_data = self._get_record_data(
                    db, result.matched_with_type, result.matched_with_id
                )

            # Run AI analysis
            analysis = self.analyze_mismatch(
                result.record_type, record_data, candidate_data
            )

            # Determine new status based on confidence
            old_status = result.status
            confidence = analysis["confidence"]

            if analysis["recommendation"] == "flag":
                new_status = "AI_FLAGGED"
            elif confidence >= self.config.AI_CONFIDENCE_AUTO_MATCH:
                new_status = "AI_MATCHED"
            elif confidence >= self.config.AI_CONFIDENCE_REVIEW:
                new_status = "AI_FLAGGED"  # Needs human review
            else:
                new_status = "AI_FLAGGED"

            # Update the result
            result.status = new_status
            result.method = "ai"
            result.confidence = confidence
            result.explanation = analysis["explanation"]

            # Audit log
            audit = AuditLog(
                action="ai_review",
                record_type=result.record_type,
                record_id=result.record_id,
                old_state=old_status,
                new_state=new_status,
                reason=(
                    f"AI recommendation: {analysis['recommendation']} "
                    f"(confidence: {confidence:.2f}). {analysis['explanation']}"
                ),
            )
            db.add(audit)

        db.commit()
        logger.info("AI review processing complete.")

    # ------------------------------------------------------------------
    # LLM Analysis (Gemini)
    # ------------------------------------------------------------------

    def _llm_analysis(
        self, record_type: str, record_data: dict, candidate_data: dict
    ) -> dict:
        """Send the mismatch context to Gemini for analysis."""
        prompt = f"""You are a financial reconciliation expert AI. Analyze the following 
mismatch between two financial records and determine if they should be matched.

Record Type: {record_type}
Source Record: {json.dumps(record_data, indent=2, default=str)}
Candidate Match: {json.dumps(candidate_data, indent=2, default=str)}

Respond ONLY with valid JSON in this exact format:
{{
    "recommendation": "match" or "flag" or "escalate",
    "confidence": <float between 0.0 and 1.0>,
    "explanation": "<clear explanation of your reasoning>"
}}

Consider:
- Amount differences (could be fees, rounding, or errors)
- Date differences (could be processing delays)
- Description variations (could be formatting differences)
- Whether the records logically belong together

Be conservative: when in doubt, recommend "flag" for human review."""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Try to extract JSON from the response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)

            # Validate required keys
            if "recommendation" not in result:
                result["recommendation"] = "flag"
            if "confidence" not in result:
                result["confidence"] = 0.5
            if "explanation" not in result:
                result["explanation"] = "AI analysis completed."

            # Clamp confidence
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

            return result

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}. Falling back to heuristics.")
            return self._heuristic_analysis(record_type, record_data, candidate_data)

    # ------------------------------------------------------------------
    # Heuristic Fallback (no API key)
    # ------------------------------------------------------------------

    def _heuristic_analysis(
        self, record_type: str, record_data: dict, candidate_data: dict
    ) -> dict:
        """
        Rule-based heuristic analysis for when LLM is unavailable.
        Uses fuzzy string matching, date proximity, and amount closeness.
        """
        confidence_factors = []
        explanations = []

        # Amount similarity
        amount_a = float(record_data.get("amount", 0) or 0)
        amount_b = float(candidate_data.get("credit", candidate_data.get("amount", 0)) or 0)

        if amount_a > 0 and amount_b > 0:
            amount_diff_pct = abs(amount_a - amount_b) / max(amount_a, amount_b) * 100
            if amount_diff_pct <= 1:
                confidence_factors.append(0.95)
                explanations.append(f"Amounts nearly identical ({amount_diff_pct:.1f}% diff)")
            elif amount_diff_pct <= 5:
                confidence_factors.append(0.75)
                explanations.append(f"Amounts close ({amount_diff_pct:.1f}% diff, likely fees)")
            else:
                confidence_factors.append(0.3)
                explanations.append(f"Significant amount difference ({amount_diff_pct:.1f}%)")

        # Description / UTR similarity
        desc_a = str(record_data.get("utr", record_data.get("description", "")))
        desc_b = str(candidate_data.get("description", candidate_data.get("utr", "")))
        if desc_a and desc_b:
            ratio = difflib.SequenceMatcher(None, desc_a.lower(), desc_b.lower()).ratio()
            confidence_factors.append(ratio)
            if ratio > 0.8:
                explanations.append(f"Strong description match ({ratio:.0%} similarity)")
            elif ratio > 0.5:
                explanations.append(f"Partial description match ({ratio:.0%} similarity)")
            else:
                explanations.append(f"Weak description match ({ratio:.0%} similarity)")

        # Date proximity
        date_a = record_data.get("created_at") or record_data.get("date")
        date_b = candidate_data.get("date") or candidate_data.get("created_at")
        if date_a and date_b:
            try:
                if isinstance(date_a, str):
                    date_a = datetime.fromisoformat(date_a.replace("Z", ""))
                if isinstance(date_b, str):
                    date_b = datetime.fromisoformat(date_b.replace("Z", ""))
                day_diff = abs((date_a - date_b).days) if hasattr(date_a, 'days') else abs((date_a.date() if hasattr(date_a, 'date') else date_a) - (date_b.date() if hasattr(date_b, 'date') else date_b)).days
                if day_diff <= 1:
                    confidence_factors.append(0.9)
                    explanations.append("Dates match closely")
                elif day_diff <= 3:
                    confidence_factors.append(0.7)
                    explanations.append(f"Dates {day_diff} days apart (possible processing delay)")
                else:
                    confidence_factors.append(0.4)
                    explanations.append(f"Dates {day_diff} days apart (suspicious)")
            except (ValueError, TypeError):
                pass

        # Compute overall confidence
        if confidence_factors:
            confidence = sum(confidence_factors) / len(confidence_factors)
        else:
            confidence = 0.5

        # Determine recommendation
        if confidence >= 0.85:
            recommendation = "match"
        elif confidence >= 0.5:
            recommendation = "flag"
        else:
            recommendation = "escalate"

        return {
            "recommendation": recommendation,
            "confidence": round(confidence, 3),
            "explanation": "; ".join(explanations) if explanations else "Heuristic analysis completed.",
        }

    # ------------------------------------------------------------------
    # Guardrails
    # ------------------------------------------------------------------

    def _apply_guardrails(
        self, result: dict, record_data: dict, candidate_data: dict
    ) -> dict:
        """
        Enforce financial invariants that AI cannot override.

        Guardrails:
        1. Amount difference > tolerance => force flag
        2. Refund > payment => always flag
        """
        guardrail_notes = []

        # Guardrail 1: Amount tolerance
        amount_a = float(record_data.get("amount", 0) or 0)
        amount_b = float(
            candidate_data.get("credit", candidate_data.get("amount", 0)) or 0
        )

        if amount_a > 0 and amount_b > 0:
            denominator = max(abs(amount_a), abs(amount_b), 1.0)
            pct_diff = abs(amount_a - amount_b) / denominator * 100
            if pct_diff > self.config.AMOUNT_TOLERANCE_PERCENT:
                result["recommendation"] = "flag"
                guardrail_notes.append(
                    f"[GUARDRAIL] Amount difference ({pct_diff:.1f}%) exceeds "
                    f"tolerance ({self.config.AMOUNT_TOLERANCE_PERCENT}%). "
                    f"AI recommendation overridden to 'flag'."
                )

        # Guardrail 2: Refund exceeding payment
        refund_amount = float(record_data.get("refund_amount", 0) or 0)
        payment_amount = float(candidate_data.get("payment_amount", 0) or 0)
        if refund_amount > 0 and payment_amount > 0 and refund_amount > payment_amount:
            result["recommendation"] = "flag"
            guardrail_notes.append(
                f"[GUARDRAIL] Refund ({refund_amount}) exceeds payment "
                f"({payment_amount}). Forced to 'flag'."
            )

        if guardrail_notes:
            result["explanation"] = (
                result.get("explanation", "") + " " + " | ".join(guardrail_notes)
            ).strip()

        return result

    # ------------------------------------------------------------------
    # Data Retrieval Helpers
    # ------------------------------------------------------------------

    def _get_record_data(self, db: Session, record_type: str, record_id: str) -> dict:
        """Fetch a record from the database and return it as a dict."""
        try:
            if record_type == "payment":
                record = db.query(Payment).filter(Payment.payment_id == record_id).first()
            elif record_type == "settlement":
                record = (
                    db.query(Settlement)
                    .filter(Settlement.settlement_id == record_id)
                    .first()
                )
            elif record_type == "bank_entry":
                record = db.query(BankEntry).filter(BankEntry.id == int(record_id)).first()
            else:
                return {"record_type": record_type, "record_id": record_id}

            if record is None:
                return {"record_type": record_type, "record_id": record_id}

            # Convert to dict
            return {
                c.name: str(getattr(record, c.name))
                for c in record.__table__.columns
            }
        except Exception as e:
            logger.error(f"Error fetching record {record_type}/{record_id}: {e}")
            return {"record_type": record_type, "record_id": record_id}
