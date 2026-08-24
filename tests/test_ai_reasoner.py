"""
Tests for the AI Reasoning Layer — guardrails and confidence thresholds.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.core.ai_reasoner import AIReasoner


class MockConfig:
    """Mock configuration for tests."""
    GEMINI_API_KEY = None  # No API key — forces heuristic mode
    AI_CONFIDENCE_AUTO_MATCH = 0.9
    AI_CONFIDENCE_REVIEW = 0.7
    AMOUNT_TOLERANCE_PERCENT = 5.0
    DATE_TOLERANCE_DAYS = 2


@pytest.fixture
def reasoner():
    """Create an AIReasoner in heuristic fallback mode."""
    return AIReasoner(MockConfig())


# ══════════════════════════════════════════════════════════════════════
# Guardrail Tests
# ══════════════════════════════════════════════════════════════════════


class TestGuardrails:
    """Test that financial guardrails override AI recommendations."""

    def test_guardrail_blocks_large_amount_difference(self, reasoner):
        """Amount difference >5% should force recommendation to 'flag'."""
        record_data = {"amount": 10000.0, "utr": "UTR123", "created_at": "2026-08-10"}
        candidate_data = {"credit": 8000.0, "description": "RAZORPAY UTR123", "date": "2026-08-10"}

        result = reasoner.analyze_mismatch("settlement", record_data, candidate_data)

        # 20% difference — guardrail must trigger
        assert result["recommendation"] == "flag"
        assert "GUARDRAIL" in result["explanation"]

    def test_guardrail_blocks_refund_exceeding_payment(self, reasoner):
        """Refund > payment should always be flagged."""
        record_data = {"amount": 5000.0, "refund_amount": 7500.0}
        candidate_data = {"amount": 5000.0, "payment_amount": 5000.0, "credit": 5000.0}

        result = reasoner.analyze_mismatch("refund", record_data, candidate_data)

        assert result["recommendation"] == "flag"

    def test_small_amount_difference_passes_guardrail(self, reasoner):
        """Amount difference <5% should NOT trigger the guardrail."""
        record_data = {"amount": 10000.0, "utr": "UTR456", "created_at": "2026-08-10"}
        candidate_data = {"credit": 9800.0, "description": "RAZORPAY SETTLEMENT UTR456", "date": "2026-08-10"}

        result = reasoner.analyze_mismatch("settlement", record_data, candidate_data)

        # 2% difference — should pass guardrail (AI decides)
        assert "GUARDRAIL" not in result.get("explanation", "")


# ══════════════════════════════════════════════════════════════════════
# Confidence Threshold Tests
# ══════════════════════════════════════════════════════════════════════


class TestConfidenceThresholds:
    """Test confidence-based status assignment."""

    def test_high_confidence_suggests_match(self, reasoner):
        """Very similar records should get high confidence."""
        record_data = {"amount": 5000.0, "utr": "UTR789012345678", "created_at": "2026-08-10"}
        candidate_data = {"credit": 5000.0, "description": "RAZORPAY SETTLEMENT UTR789012345678", "date": "2026-08-10"}

        result = reasoner.analyze_mismatch("settlement", record_data, candidate_data)

        # Near-identical records should have high confidence
        assert result["confidence"] >= 0.7
        assert result["recommendation"] in ("match", "flag")

    def test_low_confidence_flags_record(self, reasoner):
        """Very different records should get low confidence."""
        record_data = {"amount": 50000.0, "utr": "UTR111111111111", "created_at": "2026-08-01"}
        candidate_data = {"credit": 12000.0, "description": "BANK TRANSFER MISC", "date": "2026-08-20"}

        result = reasoner.analyze_mismatch("settlement", record_data, candidate_data)

        # Very different records — guardrail should trigger due to >5% diff
        assert result["recommendation"] in ("flag", "escalate")


# ══════════════════════════════════════════════════════════════════════
# Fallback Mode Test
# ══════════════════════════════════════════════════════════════════════


class TestFallbackMode:
    """Test that heuristic fallback works without API key."""

    def test_fallback_mode_without_api_key(self, reasoner):
        """Should work without Gemini API key using heuristics."""
        assert reasoner.use_llm is False  # No API key configured

        record_data = {"amount": 3000.0, "utr": "UTR555", "created_at": "2026-08-10"}
        candidate_data = {"credit": 3000.0, "description": "RAZORPAY UTR555", "date": "2026-08-11"}

        result = reasoner.analyze_mismatch("settlement", record_data, candidate_data)

        # Should still return valid analysis
        assert "recommendation" in result
        assert "confidence" in result
        assert "explanation" in result
        assert result["recommendation"] in ("match", "flag", "escalate")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_heuristic_produces_explanation(self, reasoner):
        """Heuristic mode should produce a meaningful explanation."""
        record_data = {"amount": 7500.0, "utr": "UTR_TEST", "created_at": "2026-08-10"}
        candidate_data = {"credit": 7500.0, "description": "RAZORPAY SETTLEMENT UTR_TEST", "date": "2026-08-10"}

        result = reasoner.analyze_mismatch("settlement", record_data, candidate_data)

        assert len(result["explanation"]) > 10  # Non-trivial explanation
