"""
FastAPI API routes for the Razorpay AI Finance Controller.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.config import settings
from app.core.models import (
    ReconciliationResult,
    AuditLog,
    ReconciliationResultSchema,
    AuditLogSchema,
    ReconciliationStats,
    UploadResponse,
    ReconcileResponse,
)
from app.core.ingestion import (
    parse_payments_csv,
    parse_settlements_csv,
    parse_bank_statement_csv,
    parse_refunds_csv,
)
from app.core.reconciler import ReconciliationEngine
from app.core.ai_reasoner import AIReasoner
from app.utils.report_generator import generate_csv_report

import io

router = APIRouter(prefix="/api", tags=["Reconciliation"])


# ------------------------------------------------------------------
# Upload Endpoints
# ------------------------------------------------------------------


@router.post("/upload/{data_type}", response_model=UploadResponse)
async def upload_csv(
    data_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file for ingestion.

    Supported data_type values: payments, settlements, bank_statement, refunds
    """
    valid_types = {"payments", "settlements", "bank_statement", "refunds"}
    if data_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data_type '{data_type}'. Must be one of: {', '.join(valid_types)}",
        )

    try:
        content = await file.read()

        parsers = {
            "payments": parse_payments_csv,
            "settlements": parse_settlements_csv,
            "bank_statement": parse_bank_statement_csv,
            "refunds": parse_refunds_csv,
        }

        count = parsers[data_type](content, db)

        return UploadResponse(
            records_uploaded=count,
            message=f"Successfully uploaded {count} {data_type} records.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


# ------------------------------------------------------------------
# Reconciliation Endpoint
# ------------------------------------------------------------------


@router.post("/reconcile", response_model=ReconcileResponse)
def run_reconciliation(db: Session = Depends(get_db)):
    """
    Run the full reconciliation pipeline:
    1. Deterministic three-pass matching
    2. AI reasoning for ambiguous cases
    """
    try:
        # Step 1: Deterministic reconciliation
        engine = ReconciliationEngine(db, settings)
        stats = engine.run_full_reconciliation()

        # Step 2: AI reasoning for pending reviews
        reasoner = AIReasoner(settings)
        reasoner.process_pending_reviews(db)

        # Recompute stats after AI processing
        final_stats = engine._compute_stats()

        return ReconcileResponse(
            message="Reconciliation completed successfully.",
            stats=final_stats,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Reconciliation error: {str(e)}"
        )


# ------------------------------------------------------------------
# Results Endpoints
# ------------------------------------------------------------------


@router.get("/results", response_model=List[ReconciliationResultSchema])
def get_results(
    status: Optional[str] = Query(None, description="Filter by status"),
    record_type: Optional[str] = Query(None, description="Filter by record type"),
    method: Optional[str] = Query(None, description="Filter by method"),
    db: Session = Depends(get_db),
):
    """Get reconciliation results with optional filters."""
    query = db.query(ReconciliationResult)

    if status:
        query = query.filter(ReconciliationResult.status == status)
    if record_type:
        query = query.filter(ReconciliationResult.record_type == record_type)
    if method:
        query = query.filter(ReconciliationResult.method == method)

    results = query.order_by(ReconciliationResult.id).all()

    # Convert datetime to string for serialization
    return [
        ReconciliationResultSchema(
            id=r.id,
            record_type=r.record_type,
            record_id=r.record_id,
            status=r.status,
            matched_with_type=r.matched_with_type,
            matched_with_id=r.matched_with_id,
            method=r.method,
            confidence=r.confidence,
            explanation=r.explanation,
            mismatch_type=r.mismatch_type,
            created_at=str(r.created_at) if r.created_at else None,
        )
        for r in results
    ]


@router.get("/results/{record_id}", response_model=ReconciliationResultSchema)
def get_result_detail(record_id: str, db: Session = Depends(get_db)):
    """Get detailed reconciliation result for a specific record."""
    result = (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.record_id == record_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found.")

    return ReconciliationResultSchema(
        id=result.id,
        record_type=result.record_type,
        record_id=result.record_id,
        status=result.status,
        matched_with_type=result.matched_with_type,
        matched_with_id=result.matched_with_id,
        method=result.method,
        confidence=result.confidence,
        explanation=result.explanation,
        mismatch_type=result.mismatch_type,
        created_at=str(result.created_at) if result.created_at else None,
    )


# ------------------------------------------------------------------
# Audit Log Endpoint
# ------------------------------------------------------------------


@router.get("/audit-log", response_model=List[AuditLogSchema])
def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get the audit log entries."""
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )

    return [
        AuditLogSchema(
            id=log.id,
            action=log.action,
            record_type=log.record_type,
            record_id=log.record_id,
            old_state=log.old_state,
            new_state=log.new_state,
            reason=log.reason,
            created_at=str(log.created_at) if log.created_at else None,
        )
        for log in logs
    ]


# ------------------------------------------------------------------
# Stats Endpoint
# ------------------------------------------------------------------


@router.get("/stats", response_model=ReconciliationStats)
def get_stats(db: Session = Depends(get_db)):
    """Get reconciliation summary statistics."""
    results = db.query(ReconciliationResult).all()
    total = len(results)

    if total == 0:
        return ReconciliationStats()

    matched = sum(1 for r in results if r.status == "MATCHED")
    mismatched = sum(1 for r in results if r.status == "MISMATCH")
    unmatched = sum(1 for r in results if r.status == "UNMATCHED")
    pending = sum(1 for r in results if r.status == "PENDING_AI_REVIEW")
    ai_matched = sum(1 for r in results if r.status == "AI_MATCHED")
    ai_flagged = sum(1 for r in results if r.status == "AI_FLAGGED")

    return ReconciliationStats(
        total_records=total,
        matched=matched,
        mismatched=mismatched,
        unmatched=unmatched,
        pending_ai_review=pending,
        ai_matched=ai_matched,
        ai_flagged=ai_flagged,
        match_rate_percent=round((matched + ai_matched) / total * 100, 2) if total else 0.0,
    )


# ------------------------------------------------------------------
# Export Endpoint
# ------------------------------------------------------------------


@router.get("/export")
def export_report(db: Session = Depends(get_db)):
    """Export reconciliation results as a CSV file."""
    csv_content = generate_csv_report(db)

    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reconciliation_report.csv"},
    )


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------


@router.get("/health")
def health_check():
    """API health check."""
    return {"status": "healthy", "version": "1.0.0", "service": "Razorpay AI Finance Controller"}
