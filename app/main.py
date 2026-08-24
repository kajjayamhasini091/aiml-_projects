"""
Razorpay AI Finance Controller — FastAPI Application Entry Point.

An intelligent reconciliation engine that combines deterministic rules
with AI reasoning for financial data matching and auditing.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# Create FastAPI application
app = FastAPI(
    title="Razorpay AI Finance Controller",
    description=(
        "Intelligent financial reconciliation engine combining deterministic "
        "rules with AI reasoning. Automates payment-settlement-bank matching, "
        "refund verification, and provides full audit trails."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins for demo/development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.on_event("startup")
def on_startup():
    """Initialize the database on application startup."""
    init_db()
    logging.getLogger(__name__).info("Database initialized. API ready.")


@app.get("/", tags=["Root"])
def root():
    """API root — service information."""
    return {
        "service": "Razorpay AI Finance Controller",
        "version": "1.0.0",
        "description": "Intelligent financial reconciliation engine",
        "docs": "/docs",
        "health": "/api/health",
    }
