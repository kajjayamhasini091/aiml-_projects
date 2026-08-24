"""
Report generation utilities.
Generates CSV and summary reports from reconciliation results.
"""

import csv
import io

from sqlalchemy.orm import Session

from app.core.models import ReconciliationResult, AuditLog


def generate_csv_report(db: Session) -> str:
    """
    Generate a CSV report of all reconciliation results.

    Returns:
        CSV-formatted string ready for download.
    """
    results = db.query(ReconciliationResult).order_by(ReconciliationResult.id).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Record Type",
        "Record ID",
        "Status",
        "Matched With Type",
        "Matched With ID",
        "Method",
        "Confidence",
        "Mismatch Type",
        "Explanation",
        "Timestamp",
    ])

    # Data rows
    for r in results:
        writer.writerow([
            r.record_type,
            r.record_id,
            r.status,
            r.matched_with_type or "",
            r.matched_with_id or "",
            r.method,
            f"{r.confidence:.2f}" if r.confidence is not None else "",
            r.mismatch_type or "",
            r.explanation or "",
            str(r.created_at) if r.created_at else "",
        ])

    return output.getvalue()


def generate_summary_report(db: Session) -> dict:
    """
    Generate a summary report with key reconciliation metrics.

    Returns:
        Dictionary with summary statistics.
    """
    results = db.query(ReconciliationResult).all()
    total = len(results)

    if total == 0:
        return {
            "total_records": 0,
            "matched": 0,
            "mismatched": 0,
            "unmatched": 0,
            "pending_ai_review": 0,
            "ai_matched": 0,
            "ai_flagged": 0,
            "match_rate_percent": 0.0,
            "audit_log_entries": 0,
        }

    matched = sum(1 for r in results if r.status == "MATCHED")
    mismatched = sum(1 for r in results if r.status == "MISMATCH")
    unmatched = sum(1 for r in results if r.status == "UNMATCHED")
    pending = sum(1 for r in results if r.status == "PENDING_AI_REVIEW")
    ai_matched = sum(1 for r in results if r.status == "AI_MATCHED")
    ai_flagged = sum(1 for r in results if r.status == "AI_FLAGGED")

    audit_count = db.query(AuditLog).count()

    return {
        "total_records": total,
        "matched": matched,
        "mismatched": mismatched,
        "unmatched": unmatched,
        "pending_ai_review": pending,
        "ai_matched": ai_matched,
        "ai_flagged": ai_flagged,
        "match_rate_percent": round((matched + ai_matched) / total * 100, 2),
        "audit_log_entries": audit_count,
    }
