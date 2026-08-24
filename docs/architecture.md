# Technical Architecture — Razorpay AI Finance Controller

## System Overview

The Razorpay AI Finance Controller is a modular financial reconciliation system with four primary layers: **Ingestion**, **Reconciliation Engine**, **AI Reasoning**, and **Presentation**.

```mermaid
graph TB
    subgraph "Presentation Layer"
        A["Streamlit Dashboard"]
        B["FastAPI REST API"]
    end

    subgraph "Logic Layer"
        C["Ingestion Module"]
        D["Reconciliation Engine"]
        E["AI Reasoning Layer"]
        F["Report Generator"]
    end

    subgraph "Data Layer"
        G["SQLite Database"]
        H["CSV File Parser"]
    end

    subgraph "External"
        I["Google Gemini API"]
    end

    A --> B
    B --> C
    B --> D
    B --> E
    B --> F
    C --> H
    H --> G
    D --> G
    E --> I
    E --> G
    F --> G
```

---

## Data Flow

### Reconciliation Pipeline

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant Ingest as Ingestion
    participant Recon as Reconciler
    participant AI as AI Reasoner
    participant DB as SQLite

    User->>API: POST /upload/{type} (CSV files)
    API->>Ingest: Parse & normalize
    Ingest->>DB: Store raw records

    User->>API: POST /reconcile
    API->>Recon: Run full reconciliation

    Recon->>DB: Pass 1 — Payment ↔ Settlement
    Recon->>DB: Pass 2 — Settlement ↔ Bank
    Recon->>DB: Pass 3 — Refund Verification
    Recon-->>API: Stats (with PENDING_AI_REVIEW)

    API->>AI: Process pending reviews
    AI->>DB: Fetch ambiguous records
    alt Has Gemini API Key
        AI->>AI: LLM Analysis
    else No API Key
        AI->>AI: Heuristic Fallback
    end
    AI->>AI: Apply Guardrails
    AI->>DB: Update results + audit log
    AI-->>API: Done

    API-->>User: ReconcileResponse + Final Stats
```

---

## Database Schema

```mermaid
erDiagram
    PAYMENTS {
        int id PK
        string payment_id UK
        string order_id
        float amount
        string currency
        string status
        string method
        float fee
        float tax
        datetime created_at
    }

    SETTLEMENTS {
        int id PK
        string settlement_id UK
        float amount
        float fees
        float tax
        string utr
        datetime created_at
        text payment_ids
    }

    BANK_ENTRIES {
        int id PK
        date date
        string description
        float credit
        float debit
        float balance
    }

    REFUNDS {
        int id PK
        string refund_id UK
        string payment_id
        float amount
        string status
        datetime created_at
    }

    RECONCILIATION_RESULTS {
        int id PK
        string record_type
        string record_id
        string status
        string matched_with_type
        string matched_with_id
        string method
        float confidence
        text explanation
        string mismatch_type
        datetime created_at
    }

    AUDIT_LOG {
        int id PK
        string action
        string record_type
        string record_id
        string old_state
        string new_state
        text reason
        datetime created_at
    }

    PAYMENTS ||--o{ SETTLEMENTS : "grouped into"
    PAYMENTS ||--o{ REFUNDS : "refunded via"
    SETTLEMENTS ||--o{ BANK_ENTRIES : "credited as"
    PAYMENTS ||--o{ RECONCILIATION_RESULTS : "produces"
    SETTLEMENTS ||--o{ RECONCILIATION_RESULTS : "produces"
    REFUNDS ||--o{ RECONCILIATION_RESULTS : "produces"
    RECONCILIATION_RESULTS ||--o{ AUDIT_LOG : "logged in"
```

---

## Component Details

### 1. Ingestion Module (`app/core/ingestion.py`)
- Parses CSV files with BOM handling and whitespace normalization
- Supports multiple date formats
- Safe float parsing with comma handling
- Bulk inserts into SQLite via SQLAlchemy

### 2. Reconciliation Engine (`app/core/reconciler.py`)
- **Pass 1 (Payment ↔ Settlement):** Parses `payment_ids` JSON from settlements, matches to payment records, verifies `sum(amount - fee - tax) ≈ settlement.amount` within tolerance
- **Pass 2 (Settlement ↔ Bank):** Searches bank descriptions for UTR strings (exact + fuzzy via `difflib.SequenceMatcher`), verifies amounts and dates within configured tolerance
- **Pass 3 (Refund Verification):** Validates `refund.amount ≤ payment.amount`, detects duplicate refunds per payment
- Each pass creates `ReconciliationResult` and `AuditLog` entries

### 3. AI Reasoning Layer (`app/core/ai_reasoner.py`)
- **LLM Mode:** Sends structured prompts to Gemini 1.5 Flash with full context of both records, parses JSON response
- **Heuristic Mode:** Fuzzy string matching (descriptions), date proximity scoring, amount similarity scoring
- **Guardrails:** Amount diff > tolerance → force flag; Refund > payment → force flag. Guardrails execute AFTER AI analysis and can override any recommendation

### 4. API Layer (`app/api/routes.py`)
- RESTful FastAPI endpoints with Pydantic validation
- Dependency injection for database sessions
- StreamingResponse for CSV export

### 5. Dashboard (`frontend/dashboard.py`)
- Streamlit with Razorpay brand styling
- Plotly charts for status distribution and mismatch breakdown
- Color-coded transaction table with expandable details
- Real-time API integration

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite | Zero-config, portable, perfect for demo/prototype |
| API Framework | FastAPI | Type-safe, auto-docs, async support |
| Frontend | Streamlit | Rapid development, interactive, professional look |
| AI Provider | Gemini | Free tier, fast, good at structured output |
| Matching Strategy | Deterministic-first | Most records match exactly — AI is expensive and should only handle exceptions |
| Guardrails | Post-AI enforcement | AI sees full context but can't make unsafe decisions |
| Audit Log | Immutable append-only | Compliance requirement — decisions must be traceable |

---

## Scaling Considerations (Production)

For a production deployment, the following changes would be recommended:

1. **Database:** Migrate to PostgreSQL with TimescaleDB for time-series partitioning
2. **Task Queue:** Celery + Redis for async reconciliation of large batches
3. **Data Ingestion:** Razorpay Settlement Recon API (`/v1/settlements/recon/combined`) for real-time data
4. **Monitoring:** Prometheus metrics for match rates, latency, exception counts
5. **Security:** OAuth2 authentication, role-based access control
6. **Caching:** Redis caching for frequently accessed results
